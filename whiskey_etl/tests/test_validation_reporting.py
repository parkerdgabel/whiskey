"""Tests for validation reporting and monitoring."""

from datetime import datetime, timedelta

import pytest

from whiskey_etl.validation import ValidationError, ValidationResult
from whiskey_etl.validation_reporting import (
    ValidationQuarantine,
    ValidationReport,
    ValidationReporter,
)


class TestValidationReport:
    """Test validation report functionality."""

    def test_report_initialization(self):
        """Test report initialization."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        assert report.pipeline_name == "test_pipeline"
        assert report.start_time is not None
        assert report.end_time is None
        assert report.total_records == 0
        assert report.valid_records == 0
        assert report.invalid_records == 0

    def test_add_validation_results(self):
        """Test adding validation results to report."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        # Add valid record
        valid_result = ValidationResult(valid=True)
        report.add_validation_result({"id": 1}, valid_result)
        
        assert report.total_records == 1
        assert report.valid_records == 1
        assert report.invalid_records == 0
        
        # Add invalid record with errors
        invalid_result = ValidationResult(valid=False)
        invalid_result.add_error("email", "Invalid format", "not-an-email")
        invalid_result.add_error("age", "Out of range", 200)
        
        report.add_validation_result({"id": 2, "email": "not-an-email"}, invalid_result)
        
        assert report.total_records == 2
        assert report.valid_records == 1
        assert report.invalid_records == 1
        assert report.errors_by_field["email"] == 1
        assert report.errors_by_field["age"] == 1
        assert len(report.sample_errors) == 2  # One entry per error

    def test_quarantine_records(self):
        """Test adding quarantined records."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        errors = [
            ValidationError(
                field="email",
                message="Invalid format",
                value="not-an-email"
            )
        ]
        
        report.add_quarantined_record(
            {"id": 1, "email": "not-an-email"},
            errors
        )
        
        assert len(report.quarantined_records) == 1
        assert report.quarantined_records[0]["record"]["id"] == 1
        assert "Invalid format" in report.quarantined_records[0]["errors"][0]

    def test_report_summary(self):
        """Test report summary generation."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        # Add some data
        for i in range(10):
            if i < 7:
                report.add_validation_result({"id": i}, ValidationResult(valid=True))
            else:
                result = ValidationResult(valid=False)
                result.add_error("field1", "Error message")
                report.add_validation_result({"id": i}, result)
        
        report.finalize()
        summary = report.get_summary()
        
        assert summary["pipeline"] == "test_pipeline"
        assert summary["total_records"] == 10
        assert summary["valid_records"] == 7
        assert summary["invalid_records"] == 3
        assert summary["validation_rate"] == 70.0
        assert "field1" in summary["top_field_errors"]
        assert summary["top_field_errors"]["field1"] == 3

    def test_report_json_export(self):
        """Test JSON export of report."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        report.add_validation_result({"id": 1}, ValidationResult(valid=True))
        report.finalize()
        
        json_str = report.to_json()
        assert "test_pipeline" in json_str
        assert "total_records" in json_str

    def test_report_html_export(self):
        """Test HTML export of report."""
        report = ValidationReport(
            pipeline_name="test_pipeline",
            start_time=datetime.now()
        )
        
        # Add sample data
        result = ValidationResult(valid=False)
        result.add_error("email", "Invalid format", "bad-email")
        report.add_validation_result({"id": 1}, result)
        
        report.finalize()
        html = report.to_html()
        
        assert "<html>" in html
        assert "test_pipeline" in html
        assert "Invalid format" in html
        assert "Validation Rate" in html


class TestValidationReporter:
    """Test validation reporter functionality."""

    def test_reporter_lifecycle(self):
        """Test reporter lifecycle management."""
        reporter = ValidationReporter()
        
        # Start report
        report = reporter.start_report("pipeline1")
        assert report is not None
        assert report.pipeline_name == "pipeline1"
        assert "pipeline1" in reporter.active_reports
        
        # Get active report
        active = reporter.get_active_report("pipeline1")
        assert active is report
        
        # Finalize report
        finalized = reporter.finalize_report("pipeline1")
        assert finalized is report
        assert finalized.end_time is not None
        assert "pipeline1" not in reporter.active_reports
        assert len(reporter.reports) == 1

    def test_historical_reports(self):
        """Test retrieving historical reports."""
        reporter = ValidationReporter()
        
        # Create multiple reports
        for i in range(3):
            report = reporter.start_report(f"pipeline{i}")
            report.add_validation_result({"id": 1}, ValidationResult(valid=True))
            reporter.finalize_report(f"pipeline{i}")
        
        # Get all reports
        all_reports = reporter.get_reports()
        assert len(all_reports) == 3
        
        # Get reports for specific pipeline
        pipeline0_reports = reporter.get_reports(pipeline_name="pipeline0")
        assert len(pipeline0_reports) == 1
        assert pipeline0_reports[0].pipeline_name == "pipeline0"

    def test_aggregate_statistics(self):
        """Test aggregate statistics across runs."""
        reporter = ValidationReporter()
        
        # Create reports with different validation rates
        for i in range(5):
            report = reporter.start_report("pipeline1")
            
            # Varying validation rates
            valid_count = 7 + i
            invalid_count = 3 - min(i, 2)
            
            for _ in range(valid_count):
                report.add_validation_result({}, ValidationResult(valid=True))
            
            for j in range(invalid_count):
                result = ValidationResult(valid=False)
                result.add_error("field1", "Error")
                if j % 2 == 0:
                    result.add_error("field2", "Another error")
                report.add_validation_result({}, result)
            
            reporter.finalize_report("pipeline1")
        
        # Get aggregate stats
        stats = reporter.get_aggregate_stats("pipeline1")
        
        assert stats["run_count"] == 5
        assert stats["total_records"] > 0
        assert stats["total_valid"] > 0
        assert stats["total_invalid"] > 0
        assert "overall_validation_rate" in stats
        assert "avg_validation_rate" in stats
        assert "field1" in stats["top_field_errors"]

    def test_last_n_runs(self):
        """Test getting stats for last N runs."""
        reporter = ValidationReporter()
        
        # Create 10 reports
        for i in range(10):
            report = reporter.start_report("pipeline1")
            report.add_validation_result({}, ValidationResult(valid=True))
            reporter.finalize_report("pipeline1")
        
        # Get stats for last 3 runs
        stats = reporter.get_aggregate_stats("pipeline1", last_n_runs=3)
        assert stats["run_count"] == 3


class TestValidationQuarantine:
    """Test validation quarantine functionality."""

    def test_quarantine_basic(self):
        """Test basic quarantine operations."""
        quarantine = ValidationQuarantine(max_size=100)
        
        # Add record
        errors = [
            ValidationError("email", "Invalid format"),
            ValidationError("age", "Out of range")
        ]
        
        quarantine.add(
            {"id": 1, "email": "bad"},
            errors,
            "pipeline1"
        )
        
        # Get records
        records = quarantine.get_records()
        assert len(records) == 1
        assert records[0]["record"]["id"] == 1
        assert records[0]["pipeline"] == "pipeline1"
        assert len(records[0]["errors"]) == 2

    def test_quarantine_filtering(self):
        """Test filtering quarantined records."""
        quarantine = ValidationQuarantine()
        
        # Add records from different pipelines
        for i in range(5):
            pipeline = f"pipeline{i % 2}"
            quarantine.add(
                {"id": i},
                [ValidationError("field", "error")],
                pipeline
            )
        
        # Get all records
        all_records = quarantine.get_records()
        assert len(all_records) == 5
        
        # Get records for specific pipeline
        pipeline0_records = quarantine.get_records("pipeline0")
        assert len(pipeline0_records) == 3
        
        # Get limited records
        limited = quarantine.get_records(limit=2)
        assert len(limited) == 2

    def test_quarantine_size_limit(self):
        """Test quarantine size limits."""
        quarantine = ValidationQuarantine(max_size=3)
        
        # Add more records than max size
        for i in range(5):
            quarantine.add(
                {"id": i},
                [ValidationError("field", "error")],
                "pipeline1"
            )
        
        records = quarantine.get_records()
        assert len(records) == 3
        # Should keep the most recent records
        assert records[0]["record"]["id"] == 2
        assert records[2]["record"]["id"] == 4

    def test_quarantine_clear(self):
        """Test clearing quarantine."""
        quarantine = ValidationQuarantine()
        
        # Add records from multiple pipelines
        for i in range(6):
            pipeline = f"pipeline{i % 3}"
            quarantine.add(
                {"id": i},
                [ValidationError("field", "error")],
                pipeline
            )
        
        # Clear specific pipeline
        cleared = quarantine.clear("pipeline0")
        assert cleared == 2
        assert len(quarantine.get_records()) == 4
        
        # Clear all
        cleared = quarantine.clear()
        assert cleared == 4
        assert len(quarantine.get_records()) == 0

    def test_quarantine_reprocess(self):
        """Test reprocessing quarantined records."""
        quarantine = ValidationQuarantine()
        
        # Add records
        for i in range(3):
            quarantine.add(
                {"id": i, "value": i * 10},
                [ValidationError("value", "Too small")],
                "pipeline1"
            )
        
        # Reprocess without processor
        records = quarantine.reprocess("pipeline1")
        assert len(records) == 3
        assert records[0]["id"] == 0
        
        # Reprocess with processor
        def fix_record(record):
            record["value"] = record["value"] + 100
            record["fixed"] = True
            return record
        
        fixed_records = quarantine.reprocess("pipeline1", processor=fix_record)
        assert len(fixed_records) == 3
        assert fixed_records[0]["value"] == 100
        assert fixed_records[0]["fixed"] is True


class TestValidationIntegrationReporting:
    """Test integration of validation with reporting."""

    async def test_pipeline_with_reporting(self):
        """Test validation reporting in pipeline context."""
        from whiskey_etl.validation import RecordValidator, ValidationMode
        
        # Create reporter
        reporter = ValidationReporter()
        report = reporter.start_report("test_pipeline")
        
        # Create validator with reporting
        from whiskey_etl.validation import EmailValidator, RequiredValidator
        
        validator = RecordValidator(
            field_validators={
                "email": [RequiredValidator(), EmailValidator()]
            },
            mode=ValidationMode.MARK,
            collect_stats=True
        )
        
        # Process records
        records = [
            {"id": 1, "email": "valid@example.com"},
            {"id": 2, "email": "invalid-email"},
            {"id": 3, "email": None},
            {"id": 4, "email": "another@example.com"},
        ]
        
        for record in records:
            # Transform does the validation internally
            transformed = await validator.transform(record)
            
            # Get validation result from the transform
            if transformed:
                # Extract validation result for reporting
                validation_info = transformed.get("_validation", {})
                if "_validation" in transformed:
                    # Create result from marked record
                    result = ValidationResult(valid=validation_info.get("valid", True))
                    # Add to report
                    report.add_validation_result(record, result)
                else:
                    # Valid record
                    report.add_validation_result(record, ValidationResult(valid=True))
        
        # Finalize report
        reporter.finalize_report("test_pipeline")
        
        # Check report
        summary = report.get_summary()
        assert summary["total_records"] == 4
        
        # Get stats from validator
        stats = validator.get_stats()
        assert stats["total"] == 4