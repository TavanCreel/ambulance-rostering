"""Schedule management for relief staff rostering."""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd


class Schedule:
    """Manages schedule data and staff assignments."""

    def __init__(self, week_start_date: datetime, config: Dict):
        """Initialize schedule for a given week.
        
        Args:
            week_start_date: Monday of the week to schedule
            config: Configuration dictionary
        """
        self.week_start = week_start_date
        self.week_end = week_start_date + timedelta(days=6)
        self.config = config
        self.shifts = config.get('shifts', {})
        self.relief_staff = config.get('relief_staff', [])
        
        # Initialize data structures
        self.vacancies: List[Dict] = []
        self.assignments: Dict[str, List[Tuple]] = {s['id']: [] for s in self.relief_staff}
        self.staff_hours: Dict[str, float] = {s['id']: 0.0 for s in self.relief_staff}

    def load_vacancies_from_csv(self, csv_file: str) -> None:
        """Load vacant shifts from CSV file.
        
        Expected CSV columns: date, day_of_week, shift, role, status
        """
        df = pd.read_csv(csv_file)
        self.vacancies = []
        
        for _, row in df.iterrows():
            if row.get('status') == 'VACANT':
                shift_date = pd.to_datetime(row['date'])
                self.vacancies.append({
                    'date': shift_date,
                    'day_of_week': row['day_of_week'],
                    'shift_type': row['shift'],
                    'role': row['role'],
                    'hours': self.shifts.get(row['shift'], {}).get('hours', 0),
                    'assigned_staff': None
                })

    def assign_vacancy(self, vacancy_index: int, staff_id: str) -> bool:
        """Assign a relief staff member to a vacancy.
        
        Args:
            vacancy_index: Index in the vacancies list
            staff_id: Relief staff member ID
            
        Returns:
            True if assignment successful, False otherwise
        """
        if vacancy_index >= len(self.vacancies):
            return False

        vacancy = self.vacancies[vacancy_index]
        shift_hours = vacancy['hours']
        
        # Update vacancy
        vacancy['assigned_staff'] = staff_id
        
        # Update staff tracking
        self.assignments[staff_id].append(
            (vacancy['date'], vacancy['shift_type'], shift_hours)
        )
        self.staff_hours[staff_id] += shift_hours
        
        return True

    def get_staff_assignment_count(self, staff_id: str) -> int:
        """Get number of shifts assigned to a staff member."""
        return len(self.assignments.get(staff_id, []))

    def get_staff_hours(self, staff_id: str) -> float:
        """Get total hours assigned to a staff member."""
        return self.staff_hours.get(staff_id, 0.0)

    def get_unassigned_vacancies(self) -> List[Dict]:
        """Get all vacancies not yet assigned."""
        return [v for v in self.vacancies if v['assigned_staff'] is None]

    def get_staff_schedule(self, staff_id: str) -> List[Tuple]:
        """Get schedule for a specific staff member.
        
        Returns:
            List of (date, shift_type, hours) tuples
        """
        return self.assignments.get(staff_id, [])

    def get_target_hours(self, staff_id: str) -> float:
        """Get target weekly hours for a staff member."""
        for staff in self.relief_staff:
            if staff['id'] == staff_id:
                return staff.get('target_hours_per_week', 0.0)
        return 0.0

    def get_hours_remaining(self, staff_id: str) -> float:
        """Get remaining hours available for a staff member this week."""
        target = self.get_target_hours(staff_id)
        current = self.get_staff_hours(staff_id)
        return target - current

    def to_dataframe(self) -> pd.DataFrame:
        """Convert assignments to DataFrame.
        
        Returns:
            DataFrame with columns: date, day_of_week, shift, role, assigned_staff, hours
        """
        rows = []
        for vacancy in self.vacancies:
            rows.append({
                'date': vacancy['date'],
                'day_of_week': vacancy['day_of_week'],
                'shift': vacancy['shift_type'],
                'role': vacancy['role'],
                'assigned_staff': vacancy['assigned_staff'],
                'hours': vacancy['hours']
            })
        return pd.DataFrame(rows)

    def get_workload_summary(self) -> pd.DataFrame:
        """Generate workload summary for all relief staff.
        
        Returns:
            DataFrame with columns: staff_id, role, target_hours, assigned_hours, 
                                   deviation, hours_remaining, total_shifts
        """
        data = []
        for staff in self.relief_staff:
            staff_id = staff['id']
            target = staff['target_hours_per_week']
            assigned = self.get_staff_hours(staff_id)
            role = staff['role']
            shifts = self.get_staff_assignment_count(staff_id)
            
            data.append({
                'staff_id': staff_id,
                'role': role,
                'target_hours': target,
                'assigned_hours': assigned,
                'deviation': assigned - target,
                'hours_remaining': target - assigned,
                'total_shifts': shifts
            })
        
        return pd.DataFrame(data)

    def get_unassigned_count(self) -> int:
        """Get count of unassigned vacancies."""
        return len(self.get_unassigned_vacancies())

    def get_assigned_count(self) -> int:
        """Get count of assigned vacancies."""
        return len(self.vacancies) - self.get_unassigned_count()

    def get_total_hours_assigned(self) -> float:
        """Get total hours assigned across all staff."""
        return sum(self.staff_hours.values())
