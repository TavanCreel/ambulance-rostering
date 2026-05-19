"""Constraint validation for relief staff rostering."""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class ConstraintValidator:
    """Validates rostering constraints."""

    def __init__(self, config: Dict):
        """Initialize validator with configuration.
        
        Args:
            config: Configuration dictionary with constraint settings
        """
        self.config = config
        self.constraints = config.get('constraints', {})
        self.max_consecutive = self.constraints.get('max_consecutive_shifts', 5)
        self.min_hours_between = self.constraints.get('min_hours_between_shifts', 11)
        self.min_rest_after_nights = self.constraints.get('min_rest_days_after_nights', 2)
        self.enforce_night_to_day = self.constraints.get('enforce_night_to_day_rest', True)
        self.night_to_day_rest_hours = self.constraints.get('night_to_day_min_rest_hours', 36)

    def can_assign_shift(self, staff_id: str, shift_date: datetime, shift_type: str,
                        staff_schedule: List[Tuple], staff_role: str,
                        vacancy_role: str, target_hours: float,
                        current_hours: float, shift_hours: float) -> Tuple[bool, str]:
        """Check if a staff member can be assigned to a shift.
        
        Args:
            staff_id: Relief staff identifier
            shift_date: Date of the shift
            shift_type: Shift type (EARLY, NIGHT, DAY)
            staff_schedule: List of (date, shift_type, hours) tuples for staff
            staff_role: Staff member's role (PARAMEDIC or TECHNICIAN)
            vacancy_role: Role required for vacancy
            target_hours: Target weekly hours for this staff member
            current_hours: Current assigned hours this week
            shift_hours: Hours for this shift
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Check role matching
        if staff_role != vacancy_role:
            return False, f"Role mismatch: {staff_role} cannot cover {vacancy_role}"

        # Check weekly capacity
        if current_hours + shift_hours > target_hours:
            return False, f"Would exceed target ({current_hours + shift_hours} > {target_hours})"

        # Check consecutive shifts
        consecutive = self._count_consecutive_shifts(staff_schedule, shift_date)
        if consecutive >= self.max_consecutive:
            return False, f"Would exceed max consecutive shifts ({consecutive + 1} > {self.max_consecutive})"

        # Check hours between shifts
        hours_since_last = self._hours_since_last_shift(staff_schedule, shift_date)
        if hours_since_last is not None and hours_since_last < self.min_hours_between:
            return False, f"Insufficient rest ({hours_since_last}h < {self.min_hours_between}h minimum)"

        # Check night-to-day transition
        if self.enforce_night_to_day:
            valid, reason = self._check_night_to_day_transition(staff_schedule, shift_date, shift_type)
            if not valid:
                return False, reason

        # Check rest days after nights (only if not assigning another night shift)
        if shift_type != 'NIGHT':
            valid, reason = self._check_rest_days_after_nights(staff_schedule, shift_date, shift_type)
            if not valid:
                return False, reason

        return True, "OK"

    def _count_consecutive_shifts(self, schedule: List[Tuple], shift_date: datetime) -> int:
        """Count consecutive shifts up to (but not including) the given date."""
        if not schedule:
            return 0

        sorted_schedule = sorted(schedule, key=lambda x: x[0], reverse=True)
        consecutive = 0

        for i, (date, shift_type, hours) in enumerate(sorted_schedule):
            if date >= shift_date:
                continue
            if i == 0 or (sorted_schedule[i - 1][0] - date).days == 1:
                consecutive += 1
            else:
                break

        return consecutive

    def _hours_since_last_shift(self, schedule: List[Tuple], shift_date: datetime) -> float:
        """Calculate hours since last shift. Returns None if no previous shift."""
        if not schedule:
            return None

        # Filter shifts before the target date
        previous_shifts = [s for s in schedule if s[0] < shift_date]
        if not previous_shifts:
            return None

        last_shift_date = max(previous_shifts, key=lambda x: x[0])[0]
        hours = (shift_date - last_shift_date).total_seconds() / 3600
        return hours

    def _check_night_to_day_transition(self, schedule: List[Tuple], shift_date: datetime,
                                       shift_type: str) -> Tuple[bool, str]:
        """Check night-to-day transition constraint.
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if shift_type not in ['EARLY', 'DAY']:
            return True, ""

        # Look for recent NIGHT shifts
        for prev_date, prev_shift_type, _ in schedule:
            if prev_shift_type != 'NIGHT':
                continue

            hours_since_night = (shift_date - prev_date).total_seconds() / 3600
            if hours_since_night < self.night_to_day_rest_hours:
                return False, f"Night→Day transition too soon ({hours_since_night}h < {self.night_to_day_rest_hours}h)"

        return True, ""

    def _check_rest_days_after_nights(self, schedule: List[Tuple], shift_date: datetime,
                                      shift_type: str) -> Tuple[bool, str]:
        """Check that staff have at least min_rest_days_after_nights rest days after their last night shift.
        
        Only enforces rest when assigning non-night shifts (allows consecutive nights).
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Find the most recent night shift
        night_shifts = [(s[0], s[2]) for s in schedule if s[1] == 'NIGHT']
        if not night_shifts:
            return True, ""

        last_night_date, _ = max(night_shifts, key=lambda x: x[0])
        days_since_night = (shift_date - last_night_date).days

        if days_since_night < self.min_rest_after_nights:
            return False, f"Insufficient rest after nights ({days_since_night}d < {self.min_rest_after_nights}d)"

        return True, ""

    def validate_final_schedule(self, staff_schedules: Dict[str, List[Tuple]]) -> List[str]:
        """Validate entire schedule for violations.
        
        Args:
            staff_schedules: Dict mapping staff_id to list of (date, shift_type, hours) tuples
            
        Returns:
            List of violation messages
        """
        violations = []

        for staff_id, schedule in staff_schedules.items():
            # Check consecutive shifts
            sorted_sched = sorted(schedule, key=lambda x: x[0])
            consecutive = 1
            for i in range(1, len(sorted_sched)):
                if (sorted_sched[i][0] - sorted_sched[i - 1][0]).days == 1:
                    consecutive += 1
                    if consecutive > self.max_consecutive:
                        violations.append(
                            f"{staff_id}: {consecutive} consecutive shifts exceeds max {self.max_consecutive}"
                        )
                else:
                    consecutive = 1

            # Check hours between shifts
            for i in range(1, len(sorted_sched)):
                hours_between = (sorted_sched[i][0] - sorted_sched[i - 1][0]).total_seconds() / 3600
                if hours_between < self.min_hours_between:
                    violations.append(
                        f"{staff_id}: Only {hours_between}h between shifts, minimum {self.min_hours_between}h"
                    )

        return violations
