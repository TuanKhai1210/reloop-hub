# Merge guide

Keep this application in a `frontend/` directory inside the ReLoop Hub repository. Do not copy its `README.md` or `.gitignore` over the backend root files.

## 1. Create the integration branch

```powershell
git switch dev
git pull --ff-only origin dev
git switch -c feature/frontend-prototype
```

## 2. Copy the package

Copy the delivered `frontend` directory to:

```text
F:\Github\reloop-hub\frontend
```

Do not copy `node_modules` or `dist`.

## 3. Configure the prototype

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
```

For the standalone Round 2 demonstration:

```text
VITE_DEMO_MODE=true
```

For the FastAPI backend:

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000
```

The backend `.env` must allow the Vite origin:

```text
CORS_ORIGINS=http://localhost:5173
```

## 4. Validate before committing

```powershell
npm run lint
npm test
npm run build
```

Expected result:

```text
lint: 0 errors
tests: 7 passed
build: successful
```

## 5. Commit and open the pull request

```powershell
Set-Location ..
git add frontend
git diff --cached --check
git commit -m "feat(frontend): add ReLoop Hub operations prototype"
git push -u origin feature/frontend-prototype
```

Open a pull request with:

```text
base: dev
compare: feature/frontend-prototype
```

Before merging, run both backend and frontend validation. The frontend's demo figures are labelled sample data; real impact figures appear only when connected mode reads them from FastAPI.
