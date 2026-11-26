Absolutely! If you have updated your model classes, you need to generate a new Alembic migration and apply it to your database so the schema matches your models.
Here’s the step-by-step process:

1. Make Sure Your Database Is Up-to-Date
   If you have already reset your database and it’s empty (except for alembic_version), you can skip to step 2.
   If not, make sure your DB is at the latest migration:

   **alembic upgrade head**

2. Generate a New Migration
   This will detect changes in your models and create a migration script:

   **alembic revision --autogenerate -m "Update schema for new model changes"**

   This will create a new file in backend/alembic/versions/.
   Review the generated migration to ensure it matches your intended changes.

3. Apply the Migration

   **alembic upgrade head**

   This will apply the new migration and update your database schema.

4. (Optional) Verify

   Use your app, or a tool like pgAdmin, to check that the tables and columns match your updated models.
