"""Validation reporting and monitoring for ETL pipelines."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .validation import ValidationError, ValidationResult


@dataclass
class ValidationReport:
    """Comprehensive validation report for a pipeline run."""

    pipeline_name: str
    start_time: datetime
    end_time: datetime | None = None
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    warnings_count: int = 0
    errors_by_field: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    sample_errors: list[dict[str, Any]] = field(default_factory=list)
    quarantined_records: list[dict[str, Any]] = field(default_factory=list)

    def add_validation_result(self, record: dict[str, Any], result: ValidationResult) -> None:
        """Add a validation result to the report."""
        self.total_records += 1

        if result.valid:
            self.valid_records += 1
        else:
            self.invalid_records += 1

            # Track errors
            for error in result.errors:
                self.errors_by_field[error.field] += 1
                if error.rule:
                    self.errors_by_type[error.rule] += 1

                # Store sample errors (up to 10)
                if len(self.sample_errors) < 10:
                    self.sample_errors.append({
                        "record": record,
                        "error": str(error),
                        "field": error.field,
                        "value": error.value,
                    })

        if result.warnings:
            self.warnings_count += len(result.warnings)

    def add_quarantined_record(self, record: dict[str, Any], errors: list[ValidationError]) -> None:
        """Add a quarantined record."""
        self.quarantined_records.append({
            "record": record,
            "errors": [str(e) for e in errors],
            "timestamp": datetime.now().isoformat(),
        })

    def finalize(self) -> None:
        """Finalize the report."""
        self.end_time = datetime.now()

    def get_summary(self) -> dict[str, Any]:
        """Get report summary."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "pipeline": self.pipeline_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "validation_rate": (
                self.valid_records / self.total_records * 100
                if self.total_records > 0 else 0
            ),
            "warnings_count": self.warnings_count,
            "top_field_errors": dict(
                sorted(
                    self.errors_by_field.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            ),
            "top_error_types": dict(
                sorted(
                    self.errors_by_type.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            ),
            "sample_errors": self.sample_errors[:5],
            "quarantined_count": len(self.quarantined_records),
        }

    def to_json(self) -> str:
        """Convert report to JSON."""
        return json.dumps(self.get_summary(), indent=2, default=str)

    def to_html(self) -> str:
        """Generate HTML report."""
        summary = self.get_summary()

        html = f"""
        <html>
        <head>
            <title>Validation Report - {self.pipeline_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: white; }}
                .error {{ color: #d9534f; }}
                .warning {{ color: #f0ad4e; }}
                .success {{ color: #5cb85c; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Validation Report: {self.pipeline_name}</h1>
            
            <div class="summary">
                <h2>Summary</h2>
                <div class="metric">
                    <strong>Total Records:</strong> {summary['total_records']}
                </div>
                <div class="metric">
                    <strong>Valid:</strong> <span class="success">{summary['valid_records']}</span>
                </div>
                <div class="metric">
                    <strong>Invalid:</strong> <span class="error">{summary['invalid_records']}</span>
                </div>
                <div class="metric">
                    <strong>Validation Rate:</strong> {summary['validation_rate']:.1f}%
                </div>
                <div class="metric">
                    <strong>Warnings:</strong> <span class="warning">{summary['warnings_count']}</span>
                </div>
            </div>
            
            <h2>Top Field Errors</h2>
            <table>
                <tr><th>Field</th><th>Error Count</th></tr>
        """

        for field, count in summary['top_field_errors'].items():
            html += f"<tr><td>{field}</td><td>{count}</td></tr>"

        html += """
            </table>
            
            <h2>Sample Errors</h2>
            <table>
                <tr><th>Field</th><th>Error</th><th>Value</th></tr>
        """

        for error in summary['sample_errors']:
            html += f"""
                <tr>
                    <td>{error['field']}</td>
                    <td>{error['error']}</td>
                    <td>{error.get('value', 'N/A')}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html


class ValidationReporter:
    """Handles validation reporting across pipelines."""

    def __init__(self):
        self.reports: dict[str, ValidationReport] = {}
        self.active_reports: dict[str, ValidationReport] = {}

    def start_report(self, pipeline_name: str) -> ValidationReport:
        """Start a new validation report."""
        report = ValidationReport(
            pipeline_name=pipeline_name,
            start_time=datetime.now()
        )
        self.active_reports[pipeline_name] = report
        return report

    def get_active_report(self, pipeline_name: str) -> ValidationReport | None:
        """Get active report for pipeline."""
        return self.active_reports.get(pipeline_name)

    def finalize_report(self, pipeline_name: str) -> ValidationReport | None:
        """Finalize and store report."""
        report = self.active_reports.pop(pipeline_name, None)
        if report:
            report.finalize()
            self.reports[f"{pipeline_name}_{report.start_time.isoformat()}"] = report
        return report

    def get_reports(
        self,
        pipeline_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> list[ValidationReport]:
        """Get historical reports."""
        reports = []

        for key, report in self.reports.items():
            # Filter by pipeline name
            if pipeline_name and report.pipeline_name != pipeline_name:
                continue

            # Filter by date range
            if start_date and report.start_time < start_date:
                continue
            if end_date and report.start_time > end_date:
                continue

            reports.append(report)

        return sorted(reports, key=lambda r: r.start_time, reverse=True)

    def get_aggregate_stats(
        self,
        pipeline_name: str | None = None,
        last_n_runs: int | None = None
    ) -> dict[str, Any]:
        """Get aggregate statistics across multiple runs."""
        reports = self.get_reports(pipeline_name)

        if last_n_runs:
            reports = reports[:last_n_runs]

        if not reports:
            return {}

        total_records = sum(r.total_records for r in reports)
        total_valid = sum(r.valid_records for r in reports)
        total_invalid = sum(r.invalid_records for r in reports)

        # Aggregate field errors
        field_errors = defaultdict(int)
        for report in reports:
            for field, count in report.errors_by_field.items():
                field_errors[field] += count

        return {
            "run_count": len(reports),
            "total_records": total_records,
            "total_valid": total_valid,
            "total_invalid": total_invalid,
            "overall_validation_rate": (
                total_valid / total_records * 100 if total_records > 0 else 0
            ),
            "avg_validation_rate": (
                sum(r.valid_records / r.total_records * 100
                    for r in reports if r.total_records > 0) / len(reports)
            ),
            "top_field_errors": dict(
                sorted(field_errors.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }


class ValidationQuarantine:
    """Manages quarantined records."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.quarantine: list[dict[str, Any]] = []

    def add(
        self,
        record: dict[str, Any],
        errors: list[ValidationError],
        pipeline: str,
        timestamp: datetime | None = None
    ) -> None:
        """Add record to quarantine."""
        if len(self.quarantine) >= self.max_size:
            # Remove oldest entries
            self.quarantine = self.quarantine[-(self.max_size - 1):]

        self.quarantine.append({
            "record": record,
            "errors": [str(e) for e in errors],
            "pipeline": pipeline,
            "timestamp": (timestamp or datetime.now()).isoformat(),
        })

    def get_records(
        self,
        pipeline: str | None = None,
        limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get quarantined records."""
        records = self.quarantine

        if pipeline:
            records = [r for r in records if r["pipeline"] == pipeline]

        if limit:
            records = records[-limit:]

        return records

    def clear(self, pipeline: str | None = None) -> int:
        """Clear quarantine."""
        if pipeline:
            original_len = len(self.quarantine)
            self.quarantine = [r for r in self.quarantine if r["pipeline"] != pipeline]
            return original_len - len(self.quarantine)
        else:
            count = len(self.quarantine)
            self.quarantine.clear()
            return count

    def reprocess(
        self,
        pipeline: str | None = None,
        processor: Callable[[dict[str, Any]], Any] | None = None
    ) -> list[dict[str, Any]]:
        """Get records for reprocessing."""
        records = self.get_records(pipeline)

        if processor:
            return [processor(r["record"]) for r in records]

        return [r["record"] for r in records]
