# E-Commerce POS API

A FastAPI backend for an **in-house Point-of-Sale (POS) system** used by a small
business store. A cashier/operator uses this API to manage the product
catalogue, build a customer's order (a direct single-item purchase or a cart
checkout), collect payment (cash or online), and keep inventory consistent
across all of those flows. All money values are in **INR (₹)**.

---

## 1. What this app is

### Purpose
A backend service that turns a small store's day-to-day sales operations into a
set of REST endpoints: catalogue management, cart, ordering, and payment
collection. It is designed to sit behind a store-facing web UI (a cashier
console / web app) and expose the data + business rules that UI needs.

### Target userbase
- **Store staff (operators / cashiers)** — the people actually using the POS
  console. They are authenticated users of this API with one of three roles:
  - `SUPERADMIN` — full control (manage users, products, delete, etc.).
  - `ADMIN` — elevated staff (manage products, change passwords, etc.).
  - `USER` — regular staff (browse products, build carts, place orders).
- **Customers** are *not* authenticated users of this API. A customer is a
  guest at the counter — their details (`name`, `mobile`, `email`) are captured
  per-order on the fly. The mobile number is validated as a valid Indian mobile
  number (`phonenumbers`, parsed with region `IN`).

### Use cases
1. **Direct buy** — a customer buys a single product right away (no cart).
   Cash or online payment.
2. **Cart checkout** — a cashier builds a cart of several products for a
   customer, then checks the whole cart out in one order. Cash or online.
3. **Cash sale** — payment is settled immediately (order + payment both
   `successful` in one transaction, no gateway involved).
4. **Online sale** — order is created `pending`, the gateway returns a
   `client_secret` / `checkout_url`, the customer pays out-of-band, and the
   gateway calls back via a webhook to mark the order `successful` or `failed`.
5. **Abandoned cart cleanup** — a scheduled job restocks and clears carts that
   have been idle longer than their TTL (30 minutes).

### Roles & permissions
| Role | Can do |
|---|---|
| `USER` | browse products, use cart, place orders |
| `ADMIN` | everything a `USER` can, plus manage products, change passwords |
| `SUPERADMIN` | everything, plus manage users, delete users, promote admins |

`SUPER_ROLES = {ADMIN, SUPERADMIN}` — both are treated as "super" for
permission checks (product/user management).

### Inventory model (important)
Inventory is **reserved at the moment of adding to cart or direct-buy**, using
an atomic SQL update:

```sql
UPDATE products SET inventory = inventory - 1
WHERE id = ? AND inventory > 0 AND is_deleted IS FALSE
RETURNING id;
```

- If no row is returned → the product is out of stock (raises `ProductOutOfStock`).
- Inventory is **restocked** when a cart entry is removed/decreased, when an
  online order fails, or when a webhook reports a failed payment.
- **Cart checkout does NOT decrement inventory again** — items were already
  reserved when added to the cart. Checkout only converts the reservation into
  a sale and deletes the cart rows.

---

## 2. How to run

### Prerequisites
- Python 3.12+
- PostgreSQL (a running instance, e.g. on `localhost:5432`)
- A database user and two databases (see `.env` below)

### Environment (`.env`)
```
DATABASE_URL=postgresql+asyncpg://ecommerce_app:1234@localhost:5432/ecommerce_db
SECRET_KEY=<any-long-random-hex-string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
TEST_DATABASE_URL=postgresql+asyncpg://ecommerce_app:1234@localhost:5432/ecommerce_test
# Optional — only used by real gateway adapters (currently stubs):
# STRIPE_SECRET_KEY=...
# STRIPE_WEBHOOK_SECRET=...
# RAZORPAY_KEY_ID=...
# RAZORPAY_KEY_SECRET=...
# RAZORPAY_WEBHOOK_SECRET=...
```

> `TEST_DATABASE_URL` is required to run the test suite, and the suite refuses
> to run if it equals `DATABASE_URL` (it drops and recreates every table).

### Install
```bash
python -m pip install -r requirements.txt
```

### Create the databases & apply migrations
```bash
# create the two databases (once, with a superuser)
psql -U postgres -c "CREATE DATABASE ecommerce_db OWNER ecommerce_app;"
psql -U postgres -c "CREATE DATABASE ecommerce_test OWNER ecommerce_app;"

# apply the schema to the main database
python -m alembic upgrade head
```

### Bootstrap the first superadmin
There is **no seeding mechanism** — registration (`POST /users`) requires an
existing superadmin, so the very first superadmin must be inserted manually.
Generate a hash with the app's own hasher, then insert it:

```bash
python -c "from app.core.security import hash_password; print(hash_password('pass123'))"
```

```sql
INSERT INTO users (username, hashed_password, role, is_deleted, access_token_version, updated_date, created_date)
VALUES ('superadmin', '<printed-hash>', 'SUPERADMIN', false, 0, now(), now());
```

### Run the server
```bash
uvicorn main:app --reload
```
API at `http://localhost:8000`; interactive docs at `/docs` (Swagger) and `/redoc`.

### Run the tests
```bash
python -m pytest
```

### Functionalities (summary)
- JWT auth (access + refresh tokens, single active session per user, token
  versioning for password-change invalidation).
- Product catalogue CRUD with soft delete.
- Per-user cart with inventory reservation.
- Orders: direct buy + cart checkout, with line items and a single payment
  record per order.
- Payment gateway factory (Stripe / Razorpay / Cash; Billdesk placeholder).
- Public webhooks for Stripe & Razorpay with idempotent handling.
- APScheduler job that cleans up abandoned carts every 10 minutes.

## 3. Endpoints

All endpoints except `/health` and the payment webhooks require a valid JWT in
the `Authorization: Bearer <token>` header. `require_super` means an `ADMIN` or
`SUPERADMIN` must be the caller.

### Health
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Liveness probe. Returns `{"status":"ok"}`. |

### Auth — prefix `/users`
| Method | Path | Auth | Body | Returns | Notes |
|---|---|---|---|---|---|
| POST | `/users` | `require_super` | `{username, password}` | `201 UserResponse` | Register a new staff user. Default role `USER`. |
| POST | `/users/login` | none | `{username, password}` | `200 {access_token, refresh_token, token_type}` | Issues both tokens. Single active session — issuing a refresh token revokes prior ones. |
| POST | `/users/refresh` | none | `{refresh_token}` | `200 Token` | Rotates access + refresh tokens. |
| POST | `/users/logout` | none | `{refresh_token}` | `200 str` | Revokes the user's refresh tokens. |
| PATCH | `/users/password` | `require_super` | `{username, new_password}` | `202 UserResponse` | Admins change any non-super's password; superadmins change anyone's. Bumps `access_token_version` (invalidates old access tokens). |
| PATCH | `/users/{id}` | `get_current_user` | — | `200 UserResponse` | Promote a user to `ADMIN`. Service enforces the caller must be a super role. |
| DELETE | `/users/{id}` | `require_super` | — | `202` | Soft-delete a user. Superadmin can't be deleted; an admin can't delete itself; only superadmin can delete an admin. |

### Products — prefix `/products`
| Method | Path | Auth | Body / Params | Returns | Notes |
|---|---|---|---|---|---|
| POST | `/products` | `require_super` | `ProductCreate {name, description?, price, discount, inventory}` | `201 ProductResponse` | `price > 0`, `discount >= 0`. |
| GET | `/products` | `get_current_user` | — | `200 [ProductResponse]` | Lists non-deleted products, ordered by name. |
| GET | `/products/{id}` | `get_current_user` | — | `200 ProductResponse` | `404` if not found / soft-deleted. |
| PATCH | `/products/{id}/inventory` | `require_super` | query `?new_inventory=N` | `200` product | Sets inventory to an absolute value. |
| PATCH | `/products/{id}/details` | `require_super` | `ProductUpdate {name?, description?, price?, discount?}` | `201 ProductResponse` | Partial update (only sent fields change). |
| DELETE | `/products/{id}` | `require_super` | — | `200 ProductResponse` | Soft delete (`is_deleted = true`). |

### Cart — prefix `/cart`
Each user has one cart. Adding to cart **decrements** product inventory;
removing **restocks** it.

| Method | Path | Auth | Returns | Notes |
|---|---|---|---|---|
| POST | `/cart/{product_id}/add_product` | `get_current_user` | `200 ProductCartResponse` | Atomically decrements inventory; increments quantity if already in cart. `404` bad product, `409` out of stock. |
| GET | `/cart` | `get_current_user` | `200 [ProductCartResponse]` | Lists the current user's cart, newest first. |
| DELETE | `/cart/{product_id}/delete_product` | `get_current_user` | `200 ProductCartResponse \| str` | Decrease quantity by 1 (restocks 1). If quantity was 1, removes the entry (returns a message string). `404` if no entry. |
| DELETE | `/cart/{product_id}/delete_entry` | `get_current_user` | `200 str` | Removes the whole entry and restocks its full quantity. |
| DELETE | `/cart/empty_cart` | `get_current_user` | `200 str` | Empties the cart and restocks every line. `404` if the cart is already empty. |

### Orders — prefix `/orders`
> Route order matters: `/checkout/cart` is registered **before** `/{product_id}`
> so it isn't shadowed.

`OrderRequest` body (used by both order-creation endpoints):
```json
{
  "customer": {"name": "Abhi", "mobile": "+919876543210", "email": "abhi@example.com"},
  "method": "cash" | "online",
  "gateway": "stripe" | "razorpay" | null
}
```
Validation: `method=cash` ⇒ `gateway` must be `null`; `method=online` ⇒
`gateway` must be `stripe` or `razorpay`. `tax` is passed as a query param.

| Method | Path | Auth | Params / Body | Returns | Notes |
|---|---|---|---|---|---|
| POST | `/orders/checkout/cart` | `get_current_user` | `?tax=N`, `OrderRequest` | `200 OrderCreateResponse` | Converts the whole cart into one order. `400` empty cart, `404` a cart product no longer exists, `503` gateway down. |
| POST | `/orders/{product_id}` | `get_current_user` | `?tax=N`, `OrderRequest` | `200 OrderCreateResponse` | Direct buy of one product. `404` bad product, `403` out of stock, `503` gateway down. |
| GET | `/orders` | `get_current_user` | — | `200 [OrderDetailResponse]` | Super roles see all orders; a `USER` sees only their own. |
| GET | `/orders/{id}` | `get_current_user` | — | `200 OrderDetailResponse` | `404` if not found / not owned. |
| GET | `/orders/{id}/items` | `get_current_user` | — | `200 [OrderItemResponse]` | Line items for an order. |

`OrderCreateResponse` extends `OrderDetailResponse` with:
```json
{
  "payment": { "id":.., "gateway":.., "method":.., "amount":..,
               "status":"pending"|"successful"|"failed", "transaction_reference":.. },
  "gateway_client": {"client_secret":"..."} | {"checkout_url":"..."} | null
}
```
- Cash orders: `order_status` & `payment.status` are `successful`, `gateway_client` is `null`.
- Online orders: both are `pending`, `gateway_client` carries what the UI needs
  to collect payment from the customer.

### Payments — prefix `/payments` (public, no JWT)
| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| POST | `/payments/webhooks/stripe` | gateway webhook payload (raw body) | `200 {"status":"ok"}` | Verifies + applies the event. |
| POST | `/payments/webhooks/razorpay` | gateway webhook payload (raw body) | `200 {"status":"ok"}` | Verifies + applies the event. |

The webhook handlers read the raw body (`await request.body()`) and pass it with
the headers to the gateway adapter for verification, then call
`apply_webhook_event`. Unknown payment references are acknowledged and ignored;
duplicate deliveries are idempotent (see §4).

## 4. Payment integration flow (end to end)

### The gateway factory
`app/services/payments.py` defines an abstract `PaymentGatewayAdapter` and
concrete adapters, selected by `PaymentGatewayFactory.get(gateway)`:

```
PaymentGatewayAdapter (ABC)
├── create_payment(order, payment) -> GatewayPaymentCreateResult
│       { transaction_reference, client_secret?, checkout_url? }
└── webhook_and_verify_payment(headers, raw_body) -> GatewayWebhookEvent
        { transaction_reference, success, raw_type }

StripeAdapter   ──► client_secret   (ref "test_pi_123")
RazorpayAdapter ──► checkout_url    (ref "test_rp_123")
BilldeskAdapter ──► raises GatewayNotImplementedError
Cash            ──► no adapter (handled inline, never reaches the factory)
```

> The current adapters are **stubs** that return fake references. The client
> will provide the real SDK-backed implementations later. The contract above is
> what any real adapter must satisfy (see §5).

### Flow A — Cash sale (no gateway)
```
Client ── POST /orders/{id} or /orders/checkout/cart  (method=cash, gateway=null)
  Service:
    1. reserve inventory (atomic UPDATE ... RETURNING)
    2. INSERT order        (order_status = SUCCESSFUL)
    3. INSERT order_items
    4. INSERT payment      (status = SUCCESSFUL, gateway = CASH)
    5. (checkout only) DELETE cart rows
    6. COMMIT (single transaction)
  Return: order + payment SUCCESSFUL, gateway_client = null
```
Cash is fully synchronous and atomic — if anything fails, the whole
transaction rolls back and inventory is not touched.

### Flow B — Online sale (gateway + webhook)
```
① CREATE (synchronous, in the order request)
   Client ── POST /orders/{id} or /orders/checkout/cart  (method=online, gateway=stripe|razorpay)
   Service (Transaction 1 — Option A boundary):
     1. reserve inventory (atomic UPDATE ... RETURNING)
     2. INSERT order        (order_status = PENDING)
     3. INSERT order_items
     4. INSERT payment      (status = PENDING, gateway = stripe|razorpay)
     5. (checkout only) DELETE cart rows
     6. COMMIT  ◄── DB work is committed BEFORE any network call
   Service (network call, outside the transaction):
     7. adapter = PaymentGatewayFactory.get(gateway)
     8. result = adapter.create_payment(order, payment)
     9. store payment.transaction_reference = result.transaction_reference
    10. COMMIT (persist the reference)
   Return: order PENDING + payment PENDING + gateway_client
           ({client_secret} for stripe, {checkout_url} for razorpay)
   On adapter failure (step 8-10):
     ── new transaction ──
     restock the reserved units, set order+payment = FAILED, COMMIT
     raise PaymentGatewayError → HTTP 503

② COLLECT (out of band, between client and gateway)
   The cashier UI uses gateway_client (client_secret / checkout_url) to collect
   the customer's payment on the gateway's hosted page / SDK. The API is not
   involved in this step.

③ CONFIRM (asynchronous, gateway → API)
   Gateway ── POST /payments/webhooks/{stripe|razorpay}  (raw body)
   Router:
     raw_body = await request.body()
     adapter = PaymentGatewayFactory.get(gateway)
     event = adapter.webhook_and_verify_payment(headers, raw_body)
            → GatewayWebhookEvent { transaction_reference, success, raw_type }
     await apply_webhook_event(db, event)
   apply_webhook_event:
     1. payment = get_payment_by_reference(transaction_reference)
     2. if payment is None            → return (unknown, acknowledge & ignore)
     3. if payment.status != PENDING  → return (idempotent: already terminal)
     4. order = get order by payment.order_id
     5. if event.success:
            payment.status = SUCCESSFUL, order.order_status = SUCCESSFUL
        else:
            payment.status = FAILED,    order.order_status = FAILED
            restock_order_lines(order)   ← restock every line item
     6. COMMIT
   Return: 200 {"status":"ok"}  (always — so the gateway stops retrying)
```

### Idempotency
Webhooks can be delivered more than once. The guard at step 3 (`status != PENDING
⇒ return`) makes processing idempotent: a duplicate `success` won't double-flip
anything, and a duplicate `failure` won't restock twice. The API always returns
`200` so the gateway considers the delivery handled.

### Transaction boundary decision (Option A)
The DB transaction is committed **before** the external gateway call, and the
gateway call happens **outside** any DB transaction. Rationale: keep DB
transactions short, never hold a DB lock across a network call. The cost is a
second transaction on failure to restock + mark FAILED. This is the pattern used
by both direct buy and cart checkout.

## 5. Handover notes for a developer taking over

### Project layout
```
main.py                      FastAPI app + lifespan (scheduler start/stop)
alembic/                     migrations (env.py is async, reads settings.database_url)
app/
  core/        config, security (JWT/argon2), deps (get_current_user/require_super),
               refresh_token logic + model, Token schema
  db/          Base, async engine, SessionLocal, get_db
  models/      users, products, cart, orders(+order_items+payment_details),
               refresh_tokens
  schema/      Pydantic DTOs (user, product, cart, orders, payments)
  services/    auth, product, cart, orders (business logic), payments (factory+adapters)
  routers/     auth, product, cart, orders, payments
  exception/   domain exceptions (auth, product, cart, order, payment)
  jobs/        my_job.py (abandoned-cart cleanup)
  scheduler.py APScheduler wiring
conftest.py / tests/         pytest harness + suite
```

### Adding a new payment gateway
1. Add a value to `PaymentGateway` in `app/schema/payments.py`.
2. Add an adapter class in `app/services/payments.py` implementing
   `PaymentGatewayAdapter.create_payment` and `webhook_and_verify_payment`.
3. Add a `case PaymentGateway.X: return XAdapter()` in `PaymentGatewayFactory.get`.
4. Add a webhook route in `app/routers/payments.py` (public, no JWT) that calls
   the adapter's `webhook_and_verify_payment` then `apply_webhook_event`.
5. The `OrderRequest` validator only allows `stripe`/`razorpay` for online —
   extend it if the new gateway is an online method.
6. Add gateway keys to `Settings` (`app/core/config.py`) and `.env`.

### Replacing the stub adapters (the client's job)
The stubs return hard-coded references (`test_pi_123`, `test_rp_123`) so the
flow can be exercised end-to-end without real SDKs. To go live, replace the
bodies of `StripeAdapter` / `RazorpayAdapter`:
- `create_payment`: call the provider SDK to create a payment intent / order,
  return a real `transaction_reference` + `client_secret` / `checkout_url`.
- `webhook_and_verify_payment`: **verify the signature** using the webhook
  secret from settings (the stubs currently skip verification — this MUST be
  implemented before production), then parse the event into a
  `GatewayWebhookEvent`. Keep the `transaction_reference` stable so it matches
  what `create_payment` stored.

### First superadmin
There is no seeding. The first superadmin must be inserted via SQL (see §2).
Document this for ops — a fresh deploy has zero users and `POST /users` will
return `403` until a superadmin exists.

### Scheduled job
`app/scheduler.py` starts an `AsyncIOScheduler` in the FastAPI lifespan that runs
`my_job` every 10 minutes. `my_job` finds users whose earliest cart `expires_at`
is in the past and calls `empty_cart_for_user` (restock + delete). Cart TTL is
30 minutes (`app/models/cart.py`). The job is per-user `try/except` so one user's
failure doesn't abort the run.

### Tests
- `conftest.py` guards: refuses to run without `TEST_DATABASE_URL`, and refuses
  if it equals `DATABASE_URL`. It creates all tables once per session, truncates
  + reseeds (`superadmin`/`user1`, password `pass123`) before every test, and
  overrides `get_db` to the test engine (`NullPool` — required because
  pytest-asyncio uses a fresh event loop per test).
- The job test patches `app.jobs.my_job.SessionLocal` to the test sessionmaker
  (the job otherwise uses the production engine).
- Run: `python -m pytest` (50 tests).

### Migrations
`alembic/env.py` imports all model modules so `Base.metadata` is complete, and
uses the async engine from `settings.database_url`. Commands:
```bash
python -m alembic upgrade head        # apply
python -m alembic revision --autogenerate -m "desc"   # new migration
python -m alembic downgrade -1        # one step back
```

### Known limitations / TODOs
- **Webhook signature verification is not implemented** (stubs skip it). Must
  be added before production.
- **No seeding** for the first superadmin.
- `datetime.utcnow()` is used in several models/services — Python emits
  deprecation warnings; migrate to `datetime.now(UTC)` when convenient.
- No rate limiting, no request logging, no pagination on list endpoints.
- Single active refresh session per user (issuing a new refresh token revokes
  the old one) — document if multi-device support is ever needed.
- `OrderItems` uses a composite PK `(order_id, product_id)` — a product can't
  appear twice in the same order. Be aware if you add merge-cart logic.
- All cart restock paths (decrease, delete-entry, empty-cart, and the abandoned
  cart job) use the atomic `restock_product` helper
  (`UPDATE ... SET inventory = inventory + qty`); no read-then-set updates
  remain.

### Key conventions
- Money is `Numeric(10,2)`; `net_price` is per-unit, `total_price` is the
  qty-adjusted tax-inclusive line total. `round(..., 2)` is used for tax.
- Soft delete (`is_deleted`) for users and products; orders/payments are never
  deleted, only status-changed.
- Domain exceptions are mapped to specific HTTP codes in the routers (e.g.
  `PaymentGatewayError → 503`, `CartEmptyError → 400`, `ProductOutOfStock → 403`,
  `InvalidProductError → 404`).
- `SUPER_ROLES` (ADMIN + SUPERADMIN) gate product/user management.


