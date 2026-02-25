
## ORM conventions
- We use [Annotated Declarative Syntax](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#using-annotated-declarative-table-type-annotated-forms-for-mapped-column) to specify columns. This has the advantages that the resulting ORM objects have type annotations and everything is very readable. This means:
    - every column should have a `Mapped` type declaration, eg `MyColumn: Mapped[int]`. 
    - use `Optional` to create a nullable column, eg `MyColumn: Mapped[Optional[int]]`
    - use `mapped_column()` on the right hand side if necessary. `mapped_column()` derives the datatype and nullability from the Mapped annotation. mapped_column() is not necessary if there are no additional arguments to pass such as `index`, `unique`, or `default`.
    - specify VARCHAR lenghts on the right, eg. `MyColumn: Mapped[str] = mapped_column(String(64))` will create a `VARCHAR(64)`
    - JSON should be coded as `Mapped[Dict[str,Any]]`
    - ENUM columns should be defined as Python types. The left hand values should match the desired SQL ENUM. The right hand side is not relevant. To create `ENUM('OCT', 'CF')`:
        ```
        class FeatureModalityEnum(enum.Enum):
            OCT = 1
            CF = 2
        ```
        Then set up the column as: `MyColumn: Mapped[FeatureModalityEnum]`

- To add new relationships, take a look at how they are currently set up in the ORM. For more information refer to the [Relationship docs](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html).
- classmethods starting with `by_` are selectors. For example, `by_id` in the `ImageInstance` class will query the database and return an image object with the given ID.
- classmethods starting with `from_` are alternative constructors. For example, `from_imagesets` in the `Task` class will construct a Task object given lists of image IDs and other arguments needed to define a Task.



# Migrations

We use Alembic for database migrations.

Preferred way to apply migrations:

```bash
alembic upgrade head
```

Optional: pass an env file (see `migrations/alembic/env.py`):

```bash
alembic -x env_file=/path/to/.env upgrade head
```

## Setup

- Ensure the `alembic` command is available.
- Run Alembic commands from `orm/migrations`.

## Create a migration

1. Update ORM models (see ORM conventions above).
2. Generate migration:

   ```bash
   alembic revision --autogenerate -m "describe change"
   ```

3. Review and edit the generated file in `orm/migrations/alembic/versions`.
   - Pay extra attention to renames (Alembic may generate drop/add instead of rename).

## Test a migration

1. Prepare a test database (see `docs/src/content/docs/orm/development_and_migrations.mdx`).
2. Apply migration:

   ```bash
   alembic upgrade head
   ```

   or with env file:

   ```bash
   alembic -x env_file=/path/to/.env upgrade head
   ```

3. Validate the affected workflows (viewer/import/data integrity as relevant).

## Production

- Apply approved migrations with the same command:

  ```bash
  alembic upgrade head
  ```

  (or `-x env_file=...` for explicit target configuration).
- Alembic prompts for confirmation before DB-changing commands.
