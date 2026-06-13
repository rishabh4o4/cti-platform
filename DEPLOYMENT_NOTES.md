# Deployment Notes

## Authentication Updates
The authentication system has been updated to use a database-backed Role-Based Access Control (RBAC) model. 

**IMPORTANT**: 
1. Existing sessions are invalidated due to this update.
2. The `JWT_SECRET_KEY` should be rotated at deployment to ensure all old tokens are fully rejected.
3. The default ADMIN user is seeded automatically during database migration using `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables. Ensure these are set correctly in your `.env` file before running the application.
