"""Unit tests for constraint validation."""

import unittest
from datetime import datetime, timedelta
from constraints import ConstraintValidator


class TestConstraintValidator(unittest.TestCase):
    """Test constraint validation logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'constraints': {
                'max_consecutive_shifts': 5,
                'min_hours_between_shifts': 11,
                'rest_day_definition': 'calendar_days',
                'min_rest_days_after_nights': 2,
                'enforce_night_to_day_rest': True,
                'night_to_day_min_rest_hours': 36
            }
        }
        self.validator = ConstraintValidator(self.config)
        self.base_date = datetime(2026, 5, 18)

    def test_role_matching_paramedic(self):
        """Test that paramedics can only cover paramedic roles."""
        schedule = []
        valid, reason = self.validator.can_assign_shift(
            staff_id='P1',
            shift_date=self.base_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='PARAMEDIC',
            vacancy_role='PARAMEDIC',
            target_hours=24,
            current_hours=0,
            shift_hours=12
        )
        self.assertTrue(valid)

    def test_role_matching_mismatch(self):
        """Test that role mismatch is detected."""
        schedule = []
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=self.base_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='PARAMEDIC',
            target_hours=36,
            current_hours=0,
            shift_hours=12
        )
        self.assertFalse(valid)
        self.assertIn('Role mismatch', reason)

    def test_exceed_target_hours(self):
        """Test that exceeding target hours is detected."""
        schedule = []
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=self.base_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='TECHNICIAN',
            target_hours=24,
            current_hours=20,
            shift_hours=12  # Would exceed 24
        )
        self.assertFalse(valid)
        self.assertIn('exceed target', reason)

    def test_valid_assignment(self):
        """Test valid assignment is accepted."""
        schedule = []
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=self.base_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='TECHNICIAN',
            target_hours=36,
            current_hours=0,
            shift_hours=12
        )
        self.assertTrue(valid)

    def test_night_to_day_transition_allowed(self):
        """Test night-to-day transition with sufficient rest."""
        night_shift_date = self.base_date
        day_shift_date = night_shift_date + timedelta(hours=40)  # 40 hours later
        
        schedule = [(night_shift_date, 'NIGHT', 12)]
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=day_shift_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='TECHNICIAN',
            target_hours=36,
            current_hours=12,
            shift_hours=12
        )
        self.assertTrue(valid)

    def test_night_to_day_transition_insufficient_rest(self):
        """Test night-to-day transition with insufficient rest."""
        night_shift_date = self.base_date
        day_shift_date = night_shift_date + timedelta(hours=20)  # Only 20 hours later
        
        schedule = [(night_shift_date, 'NIGHT', 12)]
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=day_shift_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='TECHNICIAN',
            target_hours=36,
            current_hours=12,
            shift_hours=12
        )
        self.assertFalse(valid)
        self.assertIn('Night→Day transition too soon', reason)

    def test_min_hours_between_shifts(self):
        """Test minimum hours between consecutive shifts."""
        first_shift_date = self.base_date
        second_shift_date = first_shift_date + timedelta(hours=8)  # Only 8 hours later
        
        schedule = [(first_shift_date, 'EARLY', 12)]
        valid, reason = self.validator.can_assign_shift(
            staff_id='T1',
            shift_date=second_shift_date,
            shift_type='EARLY',
            staff_schedule=schedule,
            staff_role='TECHNICIAN',
            vacancy_role='TECHNICIAN',
            target_hours=36,
            current_hours=12,
            shift_hours=12
        )
        self.assertFalse(valid)
        self.assertIn('Insufficient rest', reason)


if __name__ == '__main__':
    unittest.main()
