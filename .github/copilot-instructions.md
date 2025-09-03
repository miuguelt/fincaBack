# FincaBack AI Coding Instructions

This guide helps AI agents understand the FincaBack project structure, conventions, and workflows to be more effective.

## 1. Architecture Overview

The backend is a Flask application using Flask-RESTX for API structure and SQLAlchemy for the database.

- **Application Entry Point**: `create_app()` in `app/__init__.py` is the factory function. It initializes extensions, configures logging, CORS, and JWT, and registers all API namespaces.
- **API Structure**: The API is organized into namespaces using Flask-RESTX, located in `app/namespaces/`. Each namespace handles a specific domain (e.g., `auth_namespace.py`, `animals_namespace.py`). This is the preferred way to add or modify endpoints.
- **Database Models**: All SQLAlchemy models are defined in `app/models/`. They inherit from a `base_model.py` which can be extended with common functionality.
- **Configuration**: Environment-specific settings are managed in `config.py` using classes (`DevelopmentConfig`, `ProductionConfig`, `TestingConfig`). The active config is chosen in `run.py` or `wsgi.py`.
- **Authentication**: JWT (JSON Web Tokens) is used for authentication, managed by `Flask-JWT-Extended`. The core logic for token creation, refresh, and user loading is in `app/namespaces/auth_namespace.py`. A global `before_request` hook in `app/__init__.py` enforces JWT protection on most endpoints.

## 2. Developer Workflows

### Dependencies

- Project dependencies are listed in `requirements.txt`. After adding a new dependency, run `pip install -r requirements.txt`.
- For testing, `pytest-mock` and `freezegun` are used.

### Running the Application

- **Development**: Run `python run.py` to start the Flask development server with auto-reloading. It uses an ad-hoc SSL certificate for local HTTPS.
- **Production (Docker)**: The `Dockerfile` and `Docker-compose.yml` are configured to run the application with Gunicorn. The entry point is `wsgi:app`. To build and run:
  ```bash
  docker-compose up --build
  ```

### Testing

- Tests are written using `pytest`. Test files are located in the root directory and are named `test_*.py`.
- To run all tests:
  ```bash
  pytest
  ```
- To run a specific test file:
  ```bash
  pytest test_auth_route.py
  ```
- A key testing pattern involves using the `client` fixture (defined in test files) to make requests to the API and assert responses. For time-sensitive tests (like token expiration), use `freezegun` as seen in `test_jwt_flow.py`.

## 3. Code Conventions & Patterns

- **Namespaces over Blueprints**: For new API endpoints, always use Flask-RESTX namespaces. Avoid using traditional Flask Blueprints for the API.
- **Models for Payloads**: When defining new endpoints in a namespace, use `ns.model()` to define the expected request and response payloads. This enables automatic validation and Swagger documentation. Example from `auth_namespace.py`:
  ```python
  login_model = auth_ns.model('Login', {
      'identification': fields.Integer(required=True, ...),
      'password': fields.String(required=True, ...)
  })
  ```
- **Error Handling**: Use `ns.abort(http_code, message)` within namespace resources to return standardized error responses.
- **Database Sessions**: Within Flask request contexts, use the global `db` object from `app/__init__.py` for database operations (`db.session.add()`, `db.session.commit()`).
- **Security**:
    - User password verification should use the `check_password` method on the `User` model.
    - Protected endpoints should use the `@jwt_required()` decorator from `flask_jwt_extended`.
    - Role-based access control is implemented within the global JWT protection hook in `app/__init__.py`.

By following these guidelines, you can contribute to the project effectively and consistently.
