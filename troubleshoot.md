# Troubleshooting Guide

## Common Issues

### 1. Package.json Corruption

**Symptoms:** JSON parse errors, unexpected characters
**Solution:**

```bash
cd frontend
del package.json
# Run run-frontend.bat to recreate
```

### 2. Node Modules Issues

**Symptoms:** Module not found errors
**Solution:**

```bash
cd frontend
rmdir /s /q node_modules
del package-lock.json
npm cache clean --force
npm install
```

### 3. Backend Python Issues

**Symptoms:** Module import errors
**Solution:**

```bash
cd backend
pip install flask flask-cors python-dotenv requests werkzeug
```

### 4. Port Conflicts

**Symptoms:** EADDRINUSE errors
**Solution:**

- Frontend (3000): Vite will auto-select next port
- Backend (5000): Change port in app.py

### 5. CORS Issues

**Symptoms:** Cross-origin request blocked
**Solution:** Install flask-cors: `pip install flask-cors`

## Quick Fixes

1. **Complete Clean Start:**

   ```bash
   start-clean.bat
   start.bat
   ```

2. **Backend Only:**

   ```bash
   cd backend
   python app.py
   ```

3. **Frontend Only:**
   ```bash
   run-frontend.bat
   ```

## File Structure Check
