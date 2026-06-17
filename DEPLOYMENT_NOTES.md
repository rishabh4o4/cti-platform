# Deployment Notes

## Authentication Updates
The authentication system has been updated to use a database-backed Role-Based Access Control (RBAC) model. 

**IMPORTANT**: 
1. Existing sessions are invalidated due to this update.
2. The `JWT_SECRET_KEY` should be rotated at deployment to ensure all old tokens are fully rejected.
3. The default ADMIN user is seeded automatically during database migration using `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables. Ensure these are set correctly in your `.env` file before running the application.

## Credential Rotation Procedures
When rotating credentials, follow these steps to ensure all dependent services are updated:

1. **Environment Variables (.env)**
   Update all secret keys and passwords in both root `.env` and `backend/.env`.
   Generate strong 32-character secrets using: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

2. **Postgres Database Password**
   If updating the `POSTGRES_PASSWORD`, synchronize the existing running DB container before restarting:
   ```bash
   docker-compose exec db psql -U police -d police -c "ALTER USER police WITH PASSWORD 'new_password';"
   ```

3. **Purge Old Secrets from History**
   To remove accidentally committed secrets from Git history, use:
   ```bash
   git filter-repo --path .env --invert-paths
   git filter-repo --path backend/.env --invert-paths
   git push origin --force --all
   ```
   *Note: Instruct all collaborators to re-clone the repository.*
