"""Offline schema guardrails. No engine, sessions, DDL execution, or seed data."""

import reflex as rx

import unittest

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base


class SchemaTests(unittest.TestCase):
    def test_reflex_available(self):
        self.assertTrue(callable(rx.session))

    def test_mappers_and_postgres_ddl_compile(self):
        configure_mappers()
        dialect = postgresql.dialect()
        for table in Base.metadata.sorted_tables:
            with self.subTest(table=table.name):
                self.assertTrue(
                    str(CreateTable(table).compile(dialect=dialect))
                )
                for index in table.indexes:
                    self.assertTrue(
                        str(CreateIndex(index).compile(dialect=dialect))
                    )

    def test_requested_entities_and_audit_columns(self):
        required = {
            "institutions",
            "users",
            "user_sessions",
            "problems",
            "projects",
            "teams",
            "team_memberships",
            "collaboration_requests",
            "mentor_assignments",
            "proof_entries",
            "proof_attachments",
            "reviews",
            "review_replies",
            "funding_records",
            "faculty_problem_shortlists",
            "portfolio_shares",
            "notifications",
            "institution_change_requests",
            "milestones",
            "review_panel_feedback",
        }
        self.assertTrue(required.issubset(Base.metadata.tables))
        for table in Base.metadata.tables.values():
            with self.subTest(table=table.name):
                self.assertTrue(
                    {"id", "created_at", "updated_at"}.issubset(table.c.keys())
                )
                self.assertTrue(table.c.created_at.type.timezone)
                self.assertTrue(table.c.updated_at.type.timezone)
                for constraint in table.constraints:
                    self.assertIsNotNone(constraint.name)
                    if isinstance(constraint, ForeignKeyConstraint):
                        self.assertEqual(constraint.ondelete, "RESTRICT")

    def test_workflow_vocabularies(self):
        expected = {
            "funding_records": {"awaiting_leader", "confirmed", "declined"},
            "reviews": {"open", "addressed", "resolved"},
            "collaboration_requests": {"pending", "accepted", "declined"},
        }
        for table_name, values in expected.items():
            with self.subTest(table=table_name):
                column_type = Base.metadata.tables[table_name].c.status.type
                self.assertIsInstance(column_type, Enum)
                self.assertEqual(set(column_type.enums), values)
                self.assertFalse(column_type.native_enum)
                self.assertTrue(column_type.create_constraint)
        self.assertNotIn(
            "Funded", Base.metadata.tables["projects"].c.stage.type.enums
        )

    def test_partial_unique_indexes(self):
        expected = {
            "portfolio_shares": "uq_portfolio_current_owner",
            "mentor_assignments": "uq_mentor_current_project",
            "collaboration_requests": "uq_collaboration_pending",
            "institution_change_requests": "uq_student_pending_change",
        }
        for table_name, index_name in expected.items():
            index = next(
                index
                for index in Base.metadata.tables[table_name].indexes
                if index.name == index_name
            )
            self.assertIsInstance(index, Index)
            self.assertTrue(index.unique)
            self.assertIsNotNone(index.dialect_options["postgresql"]["where"])

    def test_attachment_and_funding_guards_present(self):
        attachments = Base.metadata.tables["proof_attachments"]
        self.assertTrue(
            {"url", "storage_key", "mime_type", "size_bytes"}.issubset(
                attachments.c.keys()
            )
        )
        self.assertFalse(
            {"blob", "data", "base64", "video_bytes"}.intersection(
                attachments.c.keys()
            )
        )
        checks = " ".join(
            str(c.sqltext)
            for c in attachments.constraints
            if isinstance(c, CheckConstraint)
        )
        self.assertIn("2097152", checks)
        self.assertIn("104857600", checks)
        funding = Base.metadata.tables["funding_records"]
        self.assertEqual(funding.c.amount_lakh.type.scale, 6)
        funding_checks = " ".join(
            str(c.sqltext)
            for c in funding.constraints
            if isinstance(c, CheckConstraint)
        )
        self.assertIn("responded_by_id = leader_id", funding_checks)
        self.assertIn("length(trim(decline_note)) >= 5", funding_checks)


if __name__ == "__main__":
    unittest.main()
