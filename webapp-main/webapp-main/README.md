# Cloud Native Web Application

RESTful API for user account management with authentication support.

## Prerequisites for the app

- Python 3.11+
- PostgreSQL 15+
- pip (Python package manager)

## Dependencies

All the dependencies are listed in the `requirements.txt`:
- FastAPI - Web framework
- SQLAlchemy - ORM
- PostgreSQL driver
- BCrypt - Password hashing
- Pytest - Testing framework

## Setup Instructions

### 1. Clone your Repository
```bash
git clone git@github.com:HK-Organisation/webapp.git
cd webapp
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install the Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Database

Create a `.env` file in the root directory:
```env
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_db_name
```

### 5. Initialize Database

The database tables will be created automatically when the application starts.

## Running the Application
```bash
python app.py
```

The application will start on `http://localhost:8080`

## Running Tests

### Start the Application
```bash
python app.py
```

### Run Integration Tests (in another terminal)
```bash
pytest tests/test_integration.py -v
```

## API Endpoints

### Health Check
- `GET /healthz` - Check application health

### User Management
- `POST /v1/user` - Create new user
- `GET /v1/user/self` - Get authenticated user info (requires auth)
- `PUT /v1/user/self` - Update user info (requires auth)

## Authentication

Protected endpoints require HTTP Basic Authentication:
- Username: User's email address
- Password: User's password

## Development Workflow

1. Create feature branch from `main`
2. Make changes
3. Run tests locally
4. Push to fork
5. Create pull request
6. Wait for CI tests to pass
7. Merge after approval

## CI/CD

GitHub Actions automatically runs tests on all pull requests. Tests must pass before merging.

