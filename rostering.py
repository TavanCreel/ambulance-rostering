#!/usr/bin/env python3
"""Main rostering orchestration script."""

import sys
import json
import argparse
from datetime import datetime, timedelta
import logging

from scheduler import Schedule
from constraints import ConstraintValidator
from optimizer import Optimizer
from reporter import Reporter


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def load_config(config_file: str = 'config.json') -> dict:
    """Load configuration from JSON file."""
    with open(config_file, 'r') as f:
        return json.load(f)


def main():
    """Main rostering workflow."""
    parser = argparse.ArgumentParser(
        description='Automatic relief staff rostering for ambulance station'
    )
    parser.add_argument(
        '--rota',
        required=True,
        help='Path to CSV file with vacant shifts'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--output',
        default='output',
        help='Output directory for results (default: output)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print verbose output'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without saving files'
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Create schedule
        logger.info(f"Loading vacancies from {args.rota}")
        week_start = datetime(2026, 5, 18)  # Monday
        schedule = Schedule(week_start, config)
        schedule.load_vacancies_from_csv(args.rota)
        logger.info(f"Loaded {len(schedule.vacancies)} vacancies")

        # Initialize validator and optimizer
        validator = ConstraintValidator(config)
        optimizer = Optimizer(schedule, validator, config)

        # Run optimization
        logger.info("Running optimization...")
        results = optimizer.optimize(verbose=args.verbose)
        logger.info(
            f"Optimization complete: {results['assigned']}/{results['total_vacancies']} "
            f"vacancies assigned ({results['success_rate']*100:.1f}%)"
        )

        if results['failed_assignments']:
            logger.warning(f"Failed to assign: {', '.join(results['failed_assignments'])}")

        # Generate reports
        reporter = Reporter(schedule, validator, config)

        if not args.dry_run:
            logger.info(f"Exporting results to {args.output}")
            reporter.export_to_csv(args.output)
            reporter.export_workload_to_csv(args.output)
            reporter.export_to_json(args.output)
            reporter.generate_summary_report(args.output, results)
            logger.info("Exports complete")

        # Print summary
        print("\n")
        reporter.print_summary(results)
        print("\n")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


if __name__ == '__main__':
    sys.exit(main())
