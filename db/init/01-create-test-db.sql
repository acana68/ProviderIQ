-- Runs once, when the provideriq-pgdata volume is first initialised.
-- The test suite migrates this database and rolls back every test's writes.
CREATE DATABASE provideriq_test;
