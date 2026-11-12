# LAST LIGHT — фронт

React 19 (+ React Compiler) · TypeScript 6.0 · Vite 7 · Redux Toolkit + RTK Query · Zod · React Aria · CSS Modules · d3-scale · Vitest.
Стек и структура взяты из ТЗ (wiki `nasa/wiki/analyses/last-light-architecture.md`, §5 и §9).

## Запуск

```sh
pnpm install
cp .env.example .env.local   # по умолчанию /api; в dev Vite проксирует его на Django (localhost:8000)
pnpm dev                     # http://localhost:5173
```

Прочее: `pnpm build`, `pnpm typecheck`, `pnpm lint`, `pnpm test`.

## Структура `src/`

Организация по фичам, как в проекте `hai`. Содержимое — по ТЗ (§5.2 архитектуры).

```text
src/
├── main.tsx, App.tsx
├── app/                  # инфраструктура приложения
│   ├── store.ts          # configureStore, RootState, useAppDispatch/useAppSelector
│   └── worker/           # sim.worker.ts, protocol.ts ({requestId, planRevision, datasetId, task}), client.ts
├── features/<фича>/      # components/ (Xxx.tsx + Xxx.module.css), xApi.ts (RTK Query injectEndpoints), xSlice.ts, types.ts, mockData.ts
├── shared/
│   ├── api/baseApi.ts    # RTK Query createApi для Django API (VITE_API_URL, JWT)
│   ├── layout/           # AppShell, Header
│   ├── ui/               # общие примитивы на React Aria: Button, Badge, …
│   ├── lib/              # format.ts (только UTC), утилиты
│   └── i18n/             # словари RU/EN по ruleId (R9)
├── styles/               # tokens.css (дизайн-система §1), base.css
└── assets/
```

| Фича | Компоненты | Логика |
| --- | --- | --- |
| `plan` | `MissionPanel`, `CoordsSection`, `DateField`, `NumberSlider`, `BlackoutToggle` | `planSlice` (plan, draft, revision), ссылка на план в hash (R1) |
| `result` | `Verdict`, `KpiRow`, список диагноза | `resultSlice`, `diagnosis.ts` (возвращает `ruleId`) |
| `scene` | `Scene`, `Lander`, `Sky`, `Terrain`, `StateBadge` | `sceneState.ts` |
| `timeline` | `Timeline` (дорожки Солнце/Земля/Батарея) | `viewSlice` (selectedHour, play, speed), `timeAxis.ts` |
| `horizon` | `HorizonProfile` | — |
| `calendar` | `Calendar` | поиск даты |
| `fix` | `FixPanel` (подбор координат или ближайшей даты, плашка уходит в центр экрана) | `useCoordinateFix` из `survival` |
| `survival` | `WhyPanel`, `SurvivalVerdict`, `DataView`, `Sparkline` | `survivalApi.ts` (запросы к серверу), `missionAdapter.ts` (разбор ответа), `useSurvival.ts` |
| `datasets` | `SourcesDrawer`, метка DEMO | `datasetsApi.ts` (provenance, validation), Zod-схемы |
| `auth` | вход и регистрация | `authApi.ts`, `authSlice.ts` (JWT, §10) |
| `runs` | история запусков | `runsApi.ts`, `POST /api/runs/` (§10.2) |

Зависимости: `features → app/worker → sim`, `features → shared`. Компоненты не импортируют расчёт напрямую,
а `shared` не импортирует `features`. Тест лежит рядом с файлом: `Xxx.test.tsx`.


## Контракт с сервером

Авторизация — **сессия Django** (cookie `sessionid` + CSRF), токенов в браузере нет.
`credentials: 'include'` и заголовок `X-CSRFToken` задаёт `shared/api/baseApi.ts`.
Фронт и `/api` должны быть на одном адресе (в dev это делает прокси Vite); если API на другом
домене, на сервере нужны CORS с credentials и `CSRF_TRUSTED_ORIGINS`.

```text
GET  /api/auth/csrf/                        → cookie csrftoken
POST /api/auth/register/  {username,email,password}   → 201 (дальше фронт сам входит)
POST /api/auth/login/     {username,password}
POST /api/auth/logout/
GET  /api/datasets/, /datasets/{id}/provenance|validation/
GET|POST /api/runs/, GET|PATCH|DELETE /api/runs/{id}/
```

### Расчёт миссии

```text
POST {VITE_API_URL}/mission/
  { "latitude": number, "longitude": number, "launch_date": "…Z", "landing_date": "…Z" }
  → { "status": "SUCCESS" | "FAIL", "surface": { …лунные результаты… }, "safe_haven": {...} }
```

Координаты посадки и две даты: старт (запуск) и высадка. Перелёт не расходует лунную
батарею и не копит пыль, поэтому лунные результаты читаются из `surface`
(`missionAdapter.ts`; без `surface` читается верхний уровень). Имена полей с датами заданы
константами `LAUNCH_FIELD` / `LANDING_FIELD` в `survivalApi.ts`. Допустимые даты — с 2010-01-01
по 2035-12-31 (`plan/mockData.ts`).

`SUCCESS` — аппарат выживет. Ошибки валидации приходят как `400 { "error": "…" }` и показываются как есть.
Широта допустима от −90° до −60°; точки севернее отклоняются без запроса.

«Найти подходящие координаты» отдельной ручки не требует: точка берётся из `safe_haven.destination`
того же ответа, а если укрытия рядом нет — пробуются соседние широты на той же долготе.
Если на выбранную дату подходящих координат нет совсем, всплывающее окно предлагает ближайшую дату
высадки (до 30 суток в обе стороны, перелёт прежней длины, `findNearestDate` в `survivalApi.ts`);
план меняется только после «Выбрать эту дату».
Подписи к полям — `src/features/survival/labels.ts`.

Всё остальное тоже приходит из ответа `POST /mission/`, своих расчётов на фронте нет:

- шкала миссии, сцена, KPI — по строкам `surface.forecast.timeline` и полям `summary`, `power`,
  `dte`, `assumptions` (`missionAdapter.ts`, `buildSim`; число часов шкалы — длина ответа);
- параметры аппарата в панели плана — `surface.assumptions` (только чтение);
- календарь — по одному запросу `/mission/` на каждую из 30 дат высадки (`app/listener.ts`);
- профиль горизонта — поле `horizon_profile` / `horizon` ответа, если сервер его присылает.

Запрос уходит с тремя датами в ISO 8601 с часовым поясом (`+00:00`): `timestamp`, `launch_date`,
`landing_date` (имена — константы в `survivalApi.ts`). Имена необязательных полей строки
timeline (азимут/высота Солнца и Земли, флаг видимости Земли) собраны списками в
`missionAdapter.ts`; если сервер назовёт их иначе — правится только этот список.
