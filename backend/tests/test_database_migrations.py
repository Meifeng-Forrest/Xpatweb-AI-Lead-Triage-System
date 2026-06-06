import unittest

from app.database import SCHEMA_SQL


class DatabaseMigrationTest(unittest.TestCase):
    def test_role_consolidation_migration_is_idempotent(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS routing_rules", SCHEMA_SQL)
        self.assertIn("SELECT user_id, 'agent' FROM user_roles WHERE role IN ('lead_agent', 'team_lead')", SCHEMA_SQL)
        self.assertIn("SELECT user_id, 'reviewer' FROM user_roles WHERE role IN ('escalation_handler', 'visa_verifier')", SCHEMA_SQL)
        self.assertIn("ON CONFLICT DO NOTHING", SCHEMA_SQL)
        self.assertIn("DELETE FROM user_roles WHERE role IN ('lead_agent', 'team_lead', 'escalation_handler', 'visa_verifier')", SCHEMA_SQL)
        self.assertIn("SELECT user_id, 'superadmin' FROM user_roles WHERE role = 'admin'", SCHEMA_SQL)
        self.assertIn("DELETE FROM user_roles WHERE role = 'admin'", SCHEMA_SQL)

    def test_research_briefs_table_exists(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS research_briefs", SCHEMA_SQL)
        self.assertIn("lead_id TEXT PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE", SCHEMA_SQL)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_research_briefs_status_updated_at", SCHEMA_SQL)


if __name__ == "__main__":
    unittest.main()
