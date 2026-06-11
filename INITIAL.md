# INITIAL.md - Define Your Product

> Fill this out, then run `/generate-prp INITIAL.md`

---

## PRODUCT

**Name:** [Your product name]

**Description:** [What does it do? Who is it for?]

**Type:** SaaS / Marketplace / Platform / API

---

## TECH STACK

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python |
| Frontend | React + TypeScript + Vite |
| Database | PostgreSQL |
| Auth | JWT + Google OAuth |
| UI | Chakra UI / Tailwind |
| Payments | None / Stripe / Dodo |

---

## MODULES

### Module 1: Authentication (Built-in)

**Models:** User, RefreshToken

**Endpoints:**
- POST /auth/register, /auth/login, /auth/refresh
- GET /auth/me, /auth/google

**Pages:** /login, /register, /profile

---

### Module 2: [Your Core Module]

**Description:** [What does this module do?]

**Models:**
```
[ModelName]:
  - id, user_id (FK)
  - [field]: [type]
  - created_at, updated_at
```

**Endpoints:**
```
GET    /api/[resource]      - List all
POST   /api/[resource]      - Create
GET    /api/[resource]/{id} - Get one
PUT    /api/[resource]/{id} - Update
DELETE /api/[resource]/{id} - Delete
```

**Pages:**
```
/[resource]           - List
/[resource]/new       - Create
/[resource]/{id}      - Detail
/[resource]/{id}/edit - Edit
```

---

### Module 3: [Another Module]

[Same structure as above]

---

### Module 4: Dashboard (Optional)

**Pages:** /dashboard, /settings

---

## MVP SCOPE

Must Have:
- [x] User registration/login
- [ ] [Core feature 1]
- [ ] [Core feature 2]

---

## ACCEPTANCE CRITERIA

- [ ] Users can register and login
- [ ] Users can CRUD their [resources]
- [ ] 80%+ test coverage
- [ ] Docker builds successfully

---

## RUN

```bash
/generate-prp INITIAL.md
/execute-prp PRPs/[name]-prp.md
```
