"""Optimization engine for relief staff assignment."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import math

from scheduler import Schedule
from constraints import ConstraintValidator


class Optimizer:
    """Intelligently assigns relief staff to vacancies."""

    def __init__(self, schedule: Schedule, validator: ConstraintValidator, config: Dict):
        """Initialize optimizer.
        
        Args:
            schedule: Schedule object to assign to
            validator: ConstraintValidator for checking constraints
            config: Configuration dictionary
        """
        self.schedule = schedule
        self.validator = validator
        self.config = config
        self.optimization = config.get('optimization', {})
        self.fairness_weight = self.optimization.get('fairness_weight', 0.4)
        self.rest_weight = self.optimization.get('rest_compliance_weight', 0.35)
        self.workload_weight = self.optimization.get('workload_balance_weight', 0.25)
        self.assignments_log: List[Dict] = []

    def optimize(self, verbose: bool = False) -> Dict:
        """Run optimization to assign all vacancies.
        
        Args:
            verbose: Print assignment decisions
            
        Returns:
            Dictionary with optimization results
        """
        self.assignments_log = []
        total_vacancies = len(self.schedule.vacancies)
        assigned_count = 0
        failed_assignments = []

        # Sort vacancies by date (earliest first)
        sorted_vacancies = sorted(
            enumerate(self.schedule.vacancies),
            key=lambda x: x[1]['date']
        )

        for vacancy_idx, vacancy in sorted_vacancies:
            if vacancy['assigned_staff'] is not None:
                continue  # Already assigned

            # Find best staff member for this vacancy
            best_staff_id = self._find_best_candidate(vacancy_idx)

            if best_staff_id:
                self.schedule.assign_vacancy(vacancy_idx, best_staff_id)
                assigned_count += 1
                self.assignments_log.append({
                    'date': vacancy['date'],
                    'shift': vacancy['shift_type'],
                    'role': vacancy['role'],
                    'assigned_to': best_staff_id,
                    'hours': vacancy['hours']
                })
                if verbose:
                    print(f"✓ {vacancy['date'].date()} {vacancy['shift_type']:5} {vacancy['role']:10} → {best_staff_id}")
            else:
                failed_assignments.append(f"{vacancy['date'].date()} {vacancy['shift_type']}")
                if verbose:
                    print(f"✗ {vacancy['date'].date()} {vacancy['shift_type']:5} {vacancy['role']:10} → NO CANDIDATE")

        return {
            'total_vacancies': total_vacancies,
            'assigned': assigned_count,
            'unassigned': total_vacancies - assigned_count,
            'success_rate': assigned_count / total_vacancies if total_vacancies > 0 else 0,
            'failed_assignments': failed_assignments
        }

    def _find_best_candidate(self, vacancy_idx: int) -> Optional[str]:
        """Find the best relief staff member for a vacancy.
        
        Args:
            vacancy_idx: Index of the vacancy in the schedule
            
        Returns:
            Staff ID of best candidate, or None if no valid candidate
        """
        vacancy = self.schedule.vacancies[vacancy_idx]
        vacancy_date = vacancy['date']
        vacancy_shift = vacancy['shift_type']
        vacancy_role = vacancy['role']
        vacancy_hours = vacancy['hours']

        candidates = []

        for staff in self.schedule.relief_staff:
            staff_id = staff['id']
            staff_role = staff['role']
            target_hours = staff['target_hours_per_week']
            current_hours = self.schedule.get_staff_hours(staff_id)
            staff_schedule = self.schedule.get_staff_schedule(staff_id)

            # Check if staff can be assigned
            can_assign, _ = self.validator.can_assign_shift(
                staff_id=staff_id,
                shift_date=vacancy_date,
                shift_type=vacancy_shift,
                staff_schedule=staff_schedule,
                staff_role=staff_role,
                vacancy_role=vacancy_role,
                target_hours=target_hours,
                current_hours=current_hours,
                shift_hours=vacancy_hours
            )

            if can_assign:
                # Calculate score for this candidate
                score = self._calculate_score(
                    staff_id, vacancy_date, vacancy_shift, current_hours, target_hours
                )
                candidates.append((staff_id, score))

        if not candidates:
            return None

        # Return staff with highest score
        best_staff_id = max(candidates, key=lambda x: x[1])[0]
        return best_staff_id

    def _calculate_score(self, staff_id: str, shift_date: datetime, shift_type: str,
                        current_hours: float, target_hours: float) -> float:
        """Calculate composite score for assigning a staff member to a vacancy.
        
        Args:
            staff_id: Staff member ID
            shift_date: Date of the shift
            shift_type: Type of shift (EARLY, NIGHT, DAY)
            current_hours: Current assigned hours
            target_hours: Target weekly hours
            
        Returns:
            Score (higher is better)
        """
        scores = {}

        # Fairness score: prioritize staff below their target hours
        hours_below_target = max(0, target_hours - current_hours)
        fairness_score = hours_below_target / target_hours if target_hours > 0 else 0
        scores['fairness'] = fairness_score

        # Rest compliance score: avoid shift progression issues
        staff_schedule = self.schedule.get_staff_schedule(staff_id)
        rest_score = self._calculate_rest_score(staff_schedule, shift_date, shift_type)
        scores['rest'] = rest_score

        # Workload balance: penalize staff getting close to target
        workload_score = 1.0 - (current_hours / target_hours) if target_hours > 0 else 1.0
        workload_score = max(0, min(1.0, workload_score))  # Clamp to [0, 1]
        scores['workload'] = workload_score

        # Composite score
        composite = (
            self.fairness_weight * scores['fairness'] +
            self.rest_weight * scores['rest'] +
            self.workload_weight * scores['workload']
        )

        return composite

    def _calculate_rest_score(self, schedule: List[Tuple], shift_date: datetime,
                             shift_type: str) -> float:
        """Calculate rest compliance score for a potential assignment.
        
        Returns:
            Score from 0 (worst) to 1 (best)
        """
        if not schedule:
            return 1.0  # No previous shifts, perfect score

        # Find most recent shift
        sorted_sched = sorted(schedule, key=lambda x: x[0], reverse=True)
        last_date, last_shift_type, _ = sorted_sched[0]

        hours_since_last = (shift_date - last_date).total_seconds() / 3600

        # Penalize transitions without enough rest
        if last_shift_type == 'NIGHT' and shift_type in ['EARLY', 'DAY']:
            # Night to day transition
            min_required = self.validator.night_to_day_rest_hours
            if hours_since_last < min_required:
                penalty = 1.0 - (hours_since_last / min_required)
                return max(0, 1.0 - penalty)

        # Prefer natural progressions
        progression_preferences = {
            ('NIGHT', 'NIGHT'): 0.9,
            ('NIGHT', 'EARLY'): 0.7,
            ('EARLY', 'EARLY'): 0.95,
            ('EARLY', 'DAY'): 0.8,
            ('DAY', 'DAY'): 0.95,
            ('DAY', 'EARLY'): 0.7,
        }

        pref_score = progression_preferences.get((last_shift_type, shift_type), 0.5)
        return pref_score

    def get_assignments_log(self) -> List[Dict]:
        """Get log of all assignments made."""
        return self.assignments_log
