#!/bin/bash

alembic upgrade head --sql > sql/migrations.sql
echo "SQL for the migration generated: sql/migrations.sql"