# PharmaSUD Production Readiness Evidence

Generated from the release branch by `scripts/security_inventory.py`.

## Route Security Inventory

| Method | Path | Function | Source | Auth | Authorization | Rate | Mutates | Destructive | Exposure | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| POST | /api/medicines/upload-image | upload_medicine_image | medicines.py:232 | JWT | require_admin | none | YES | NO | authenticated | protected |
| POST | /api/medicines/ | create_medicine | medicines.py:267 | JWT | permission:medicines.create | none | YES | NO | authenticated | protected |
| GET | /api/medicines/ | list_medicines | medicines.py:328 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/medicines/barcode/{barcode} | search_by_barcode | medicines.py:370 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/medicines/{medicine_id} | get_medicine | medicines.py:396 | JWT | none | none | NO | NO | authenticated | protected |
| PUT | /api/medicines/{medicine_id} | update_medicine | medicines.py:422 | JWT | permission:medicines.edit | none | YES | NO | authenticated | protected |
| DELETE | /api/medicines/{medicine_id} | delete_medicine | medicines.py:531 | JWT | permission:medicines.delete | none | YES | YES | authenticated | protected |
| POST | /api/medicines/{medicine_id}/units | create_units | medicines.py:595 | JWT | require_admin | none | YES | NO | authenticated | protected |
| GET | /api/medicines/categories/list | get_categories | medicines.py:645 | JWT | none | none | NO | NO | authenticated | protected |
| POST | /api/batches/receive | receive_batch | batches.py:121 | JWT | none | none | YES | NO | authenticated | protected |
| POST | /api/batches/receive/confirm-short-expiry | confirm_short_expiry_batch | batches.py:249 | JWT | none | none | YES | NO | authenticated | protected |
| GET | /api/batches/available/{medicine_id} | get_available_batches | batches.py:335 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/batches/fefo-test/{medicine_id} | test_fefo | batches.py:453 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/inventory/ | get_inventory | inventory.py:113 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/inventory/{medicine_id}/batches | get_medicine_batches | inventory.py:164 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/inventory/expired | get_expired_report | inventory.py:204 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/inventory/stocktake/start | start_stocktake | inventory.py:254 | JWT | permission:inventory.adjust | none | NO | NO | authenticated | protected |
| POST | /api/inventory/stocktake/submit | submit_stocktake | inventory.py:286 | JWT | permission:inventory.adjust | none | YES | NO | authenticated | protected |
| GET | /api/settings/employees | list_employees | settings.py:52 | JWT | permission:employees.view | none | NO | NO | authenticated | protected |
| POST | /api/settings/employees | create_employee | settings.py:75 | JWT | permission:employees.manage, require_admin | none | YES | NO | authenticated | protected |
| DELETE | /api/settings/employees/{employee_id} | delete_employee | settings.py:134 | JWT | permission:employees.manage, require_admin | none | YES | YES | authenticated | protected |
| PATCH | /api/settings/employees/{employee_id}/toggle | toggle_employee_status | settings.py:196 | JWT | permission:employees.manage, require_admin | none | YES | YES | authenticated | protected |
| POST | /api/settings/change-password | change_password | settings.py:261 | JWT | none | none | YES | YES | authenticated | protected |
| GET | /api/settings/pharmacy | get_pharmacy_settings | settings.py:304 | JWT | permission:settings.view | none | NO | NO | authenticated | protected |
| PUT | /api/settings/pharmacy | update_pharmacy_settings | settings.py:332 | JWT | permission:settings.manage | none | YES | NO | authenticated | protected |
| POST | /api/sales/create | create_sale | sales.py:75 | JWT | none | none | YES | NO | authenticated | protected |
| GET | /api/sales/ | get_sales | sales.py:294 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/sales/{sale_id} | get_sale_detail | sales.py:401 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/sales/pos/search | pos_search | sales.py:481 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/sales/pos/quick-medicines | quick_medicines | sales.py:566 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/sales/pos/barcode/{barcode} | pos_barcode_search | sales.py:633 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/public/invoice/{invoice_number} | get_public_invoice | sales.py:718 | none | none | none | NO | NO | public | read-only |
| GET | /api/reports/dashboard | get_dashboard | reports.py:90 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/reports/sales | get_sales_report | reports.py:311 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/reports/profits | get_profit_report | reports.py:437 | JWT | permission:profit.view | none | NO | NO | authenticated | protected |
| GET | /api/reports/slow-moving | get_slow_moving | reports.py:535 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/reports/purchase-forecast | get_purchase_forecast | reports.py:636 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/alerts/ | get_alerts | alerts.py:22 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/alerts/count | get_alerts_count | alerts.py:101 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/employees/ | list_employees | employees.py:36 | JWT | permission:employees.view | none | NO | NO | authenticated | protected |
| POST | /api/employees/ | create_employee | employees.py:63 | JWT | permission:employees.manage, require_admin | none | YES | NO | authenticated | protected |
| PUT | /api/employees/{employee_id}/toggle | toggle_employee | employees.py:113 | JWT | permission:employees.manage, require_admin | none | YES | YES | authenticated | protected |
| PUT | /api/employees/{employee_id}/reset-password | reset_employee_password | employees.py:171 | JWT | permission:employees.manage, require_admin | none | YES | YES | authenticated | protected |
| GET | /api/audit-log/ | get_audit_log | audit.py:73 | JWT | require_admin | none | NO | NO | authenticated | protected |
| GET | /api/user/context | get_user_context | user_context.py:113 | JWT | none | none | NO | NO | authenticated | protected |
| GET | / | root | main.py:139 | none | none | none | NO | NO | public | read-only |
| GET | /api | api_info | main.py:148 | none | none | none | NO | NO | public | read-only |
| GET | /health | health | main.py:157 | none | none | none | NO | NO | public | read-only |
| GET | /ping | ping | main.py:186 | none | none | none | NO | NO | public | read-only |
| GET | /login | login_page | main.py:195 | none | none | none | NO | NO | public | read-only |
| GET | /dashboard | dashboard_page | main.py:208 | none | none | none | NO | NO | public | read-only |
| GET | /medicines | medicines_page | main.py:219 | none | none | none | NO | NO | public | read-only |
| GET | /medicine-form | medicine_form_page | main.py:230 | none | none | none | NO | NO | public | read-only |
| GET | /batch-receive | batch_receive_page | main.py:241 | none | none | none | NO | NO | public | read-only |
| GET | /inventory | inventory_page | main.py:252 | none | none | none | NO | NO | public | read-only |
| GET | /settings | settings_page | main.py:263 | none | none | none | NO | NO | public | read-only |
| GET | /pos | pos_page | main.py:274 | none | none | none | NO | NO | public | read-only |
| GET | /alerts | alerts_page | main.py:306 | none | none | none | NO | NO | public | read-only |
| GET | /employees | employees_page | main.py:317 | none | none | none | NO | NO | public | read-only |
| GET | /audit-log | audit_log_page | main.py:328 | none | none | none | NO | NO | public | read-only |
| GET | /stocktake | stocktake_page | main.py:339 | none | none | none | NO | NO | public | read-only |
| GET | /sales-history | sales_history_page | main.py:354 | none | none | none | NO | NO | public | read-only |
| GET | /reports-sales | reports_sales_page | main.py:369 | none | none | none | NO | NO | public | read-only |
| GET | /reports-profits | reports_profits_page | main.py:380 | none | none | none | NO | NO | public | read-only |
| GET | /reports-slow-moving | reports_slow_moving_page | main.py:391 | none | none | none | NO | NO | public | read-only |
| GET | /reports-purchase-forecast | purchase_forecast_page | main.py:402 | none | none | none | NO | NO | public | read-only |
| POST | /api/auth/activate | api_activate | main.py:417 | none | none | 10 per 1 minute | YES | NO | public; product-key gated | controlled onboarding |
| POST | /api/auth/setup | api_setup | main.py:423 | none | none | 5 per 1 minute | YES | NO | public; product-key gated | controlled onboarding |
| POST | /api/auth/create-pharmacy | api_create_pharmacy | main.py:438 | none | none | 5 per 1 minute | NO | NO | 404 in all environments | closed |
| POST | /api/auth/seed-demo | api_seed_demo | main.py:445 | none | none | 2 per 1 minute | NO | NO | 404 in all environments | closed |
| POST | /api/auth/login | api_login | main.py:456 | none | none | 10 per 1 minute | NO | NO | public | read-only |
| GET | /api/auth/me | api_me | main.py:462 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/rbac/me | api_rbac_me | main.py:476 | JWT | none | none | NO | NO | authenticated | protected |
| GET | /api/system/status | api_status | main.py:488 | none | none | none | NO | NO | public | read-only |

Route count: 74.

## User Mutation Inventory

| File | Line | Category | Evidence |
|---|---|---|---|
| alembic\versions\20240618_rbac_phase1.py | 65 | role_id | role_id = uuid.uuid4() |
| alembic\versions\20240618_rbac_phase1.py | 186 | raw user SQL | UPDATE users |
| alembic\versions\20240618_rbac_phase1.py | 187 | role_id | SET role_id = (SELECT id FROM roles WHERE name = 'owner') |
| alembic\versions\20240618_rbac_phase1.py | 188 | role | WHERE role = 'admin' |
| alembic\versions\20240618_rbac_phase1.py | 193 | raw user SQL | UPDATE users |
| alembic\versions\20240618_rbac_phase1.py | 194 | role_id | SET role_id = (SELECT id FROM roles WHERE name = 'cashier') |
| alembic\versions\20240618_rbac_phase1.py | 195 | role | WHERE role = 'employee' |
| alembic\versions\20240618_rbac_phase1.py | 202 | raw user SQL | UPDATE users |
| alembic\versions\20240618_rbac_phase1.py | 203 | role_id | SET role_id = (SELECT id FROM roles WHERE name = 'cashier') |
| alerts.py | 28 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| alerts.py | 47 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| alerts.py | 48 | is_active | AND b.is_active = true |
| alerts.py | 77 | is_active | AND b.is_active = true |
| alerts.py | 79 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| alerts.py | 107 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| alerts.py | 113 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| alerts.py | 114 | is_active | AND b.is_active = true |
| alerts.py | 125 | is_active | AND b.is_active = true |
| alerts.py | 127 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| audit.py | 82 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| audit.py | 84 | pharmacy_id | conditions = "WHERE a.pharmacy_id = :pid" |
| auth.py | 137 | role | if user.role == "admin": |
| auth.py | 149 | role | elif user.role == "employee": |
| auth.py | 234 | pharmacy_id | User.pharmacy_id == pharmacy.id, |
| auth.py | 235 | role | User.role == "admin" |
| auth.py | 245 | is_active | pharmacy.is_active = True |
| auth.py | 251 | pharmacy_id | db=db, pharmacy_id=str(pharmacy.id), user_id=None, user_name="system", |
| auth.py | 324 | pharmacy_id | User.pharmacy_id == pharmacy_uuid, |
| auth.py | 325 | role | User.role == "admin" |
| auth.py | 335 | username | existing_user = db.query(User).filter(User.username == username).first() |
| auth.py | 346 | user insert | new_admin = User( |
| auth.py | 348 | pharmacy_id | pharmacy_id=pharmacy_uuid, |
| auth.py | 349 | username | username=username, |
| auth.py | 351 | password_hash | password_hash=get_password_hash(password), |
| auth.py | 352 | role | role="admin", |
| auth.py | 353 | role_id | role_id=owner_role.id, |
| auth.py | 354 | is_active | is_active=True |
| auth.py | 362 | pharmacy_id | db=db, pharmacy_id=str(pharmacy_uuid), user_id=str(new_admin.id), |
| auth.py | 386 | username | user = db.query(User).filter(User.username == username).first() |
| auth.py | 443 | is_active | activated_pharmacy = db.query(Pharmacy).filter(Pharmacy.is_active == True).first() |
| auth.py | 454 | pharmacy_id | User.pharmacy_id == activated_pharmacy.id, |
| auth.py | 455 | role | User.role == "admin" |
| auth.py | 549 | pharmacy_id | pharmacy_id = activation_result['pharmacy_id'] |
| auth.py | 569 | pharmacy_id | pharmacy_id=pharmacy_id, |
| auth.py | 572 | username | username=admin_username, |
| auth.py | 589 | pharmacy_id | pharmacy_id=pharmacy_id, |
| auth.py | 591 | username | User.username == admin_username |
| batches.py | 150 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"]) |
| batches.py | 159 | is_active | Batch.is_active == True |
| batches.py | 209 | is_active | is_active=True |
| batches.py | 270 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"]) |
| batches.py | 301 | is_active | is_active=True |
| batches.py | 353 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"]) |
| batches.py | 364 | is_active | Batch.is_active == True, |
| batches.py | 413 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(pharmacy_id), |
| batches.py | 415 | is_active | Batch.is_active == True, |
| batches.py | 471 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"]) |
| batches.py | 500 | is_active | Batch.is_active == True, |
| demo\seed_demo_pharmacy.py | 91 | pharmacy_id | pharmacy_id=pharmacy_uuid, |
| demo\seed_demo_pharmacy.py | 126 | is_active | is_active=True |
| demo\seed_demo_pharmacy.py | 149 | pharmacy_id | User.pharmacy_id == pharmacy_id, |
| demo\seed_demo_pharmacy.py | 150 | username | User.username == emp_data['username'] |
| demo\seed_demo_pharmacy.py | 159 | user insert | user = User( |
| demo\seed_demo_pharmacy.py | 161 | pharmacy_id | pharmacy_id=pharmacy_id, |
| demo\seed_demo_pharmacy.py | 162 | username | username=emp_data['username'], |
| demo\seed_demo_pharmacy.py | 164 | password_hash | password_hash=get_password_hash(password), |
| demo\seed_demo_pharmacy.py | 165 | role | role=emp_data['role'], |
| demo\seed_demo_pharmacy.py | 166 | is_active | is_active=True |
| demo\seed_demo_pharmacy.py | 198 | pharmacy_id | pharmacy_id=pharmacy_id, |
| demo\seed_demo_pharmacy.py | 200 | pharmacy_id | User.pharmacy_id == pharmacy_id, |
| demo\seed_demo_pharmacy.py | 201 | role | User.role == 'admin' |
| demo\seed_demo_pharmacy.py | 204 | pharmacy_id | Sale.pharmacy_id == pharmacy_id |
| demo\seed_demo_pharmacy.py | 238 | is_active | batch.is_active = False |
| demo\seed_demo_pharmacy.py | 322 | pharmacy_id | db.query(Medicine.id).filter(Medicine.pharmacy_id == pid) |
| demo\seed_demo_pharmacy.py | 326 | pharmacy_id | db.query(Sale).filter(Sale.pharmacy_id == pid).delete(synchronize_session=False) |
| demo\seed_demo_pharmacy.py | 329 | pharmacy_id | db.query(Medicine.id).filter(Medicine.pharmacy_id == pid) |
| demo\seed_demo_pharmacy.py | 335 | pharmacy_id | db.query(Medicine.id).filter(Medicine.pharmacy_id == pid) |
| demo\seed_demo_pharmacy.py | 339 | pharmacy_id | db.query(Medicine).filter(Medicine.pharmacy_id == pid).delete(synchronize_session=False) |
| demo\seed_demo_pharmacy.py | 354 | pharmacy_id | pharmacy_id = sys.argv[1] |
| employees.py | 45 | pharmacy_id | User.pharmacy_id == ph_id |
| employees.py | 69 | role | """إنشاء موظف جديد (Admin فقط - role='employee' دائماً).""" |
| employees.py | 73 | username | existing = db.query(User).filter(User.username == data.username).first() |
| employees.py | 79 | user insert | new_user = User( |
| employees.py | 81 | pharmacy_id | pharmacy_id=ph_id, |
| employees.py | 82 | username | username=data.username, |
| employees.py | 84 | password_hash | password_hash=get_password_hash(data.password), |
| employees.py | 86 | role | role="employee", |
| employees.py | 87 | role_id | role_id=cashier_role.id, |
| employees.py | 88 | is_active | is_active=True |
| employees.py | 98 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| employees.py | 133 | pharmacy_id | User.pharmacy_id == ph_id |
| employees.py | 139 | role | if employee.role == "admin" and employee.is_active: |
| employees.py | 141 | pharmacy_id | User.pharmacy_id == ph_id, |
| employees.py | 142 | role | User.role == "admin", |
| employees.py | 143 | is_active | User.is_active == True, |
| employees.py | 149 | is_active | employee.is_active = not employee.is_active |
| employees.py | 158 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| employees.py | 188 | pharmacy_id | User.pharmacy_id == ph_id |
| employees.py | 195 | password_hash | employee.password_hash = get_password_hash(data.new_password) |
| employees.py | 201 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| generate_test_data.py | 38 | pharmacy_id | pharmacy_id = str(ph[0]) |
| generate_test_data.py | 44 | pharmacy_id | WHERE pharmacy_id = :pid AND role = 'admin' |
| generate_test_data.py | 44 | role | WHERE pharmacy_id = :pid AND role = 'admin' |
| generate_test_data.py | 56 | pharmacy_id | FROM medicines m WHERE m.pharmacy_id = :pid |
| generate_test_data.py | 71 | pharmacy_id | WHERE m.pharmacy_id = :pid AND b.is_active = true |
| generate_test_data.py | 71 | is_active | WHERE m.pharmacy_id = :pid AND b.is_active = true |
| inventory.py | 57 | is_active | Batch.is_active == True |
| inventory.py | 81 | is_active | Batch.is_active == True, |
| inventory.py | 122 | pharmacy_id | Medicine.pharmacy_id == ph_id |
| inventory.py | 135 | is_active | Batch.is_active == True |
| inventory.py | 177 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"]) |
| inventory.py | 221 | pharmacy_id | WHERE m.pharmacy_id = :pharmacy_id |
| inventory.py | 263 | pharmacy_id | Medicine.pharmacy_id == ph_id |
| inventory.py | 293 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| inventory.py | 367 | is_active | Batch.is_active == True, |
| inventory.py | 379 | is_active | batch.is_active = False |
| inventory.py | 422 | pharmacy_id | pharmacy_id=pharmacy_id, |
| main.py | 428 | pharmacy_id | pharmacy_id=data.pharmacy_id, |
| main.py | 431 | username | username=data.username, |
| main.py | 507 | pharmacy_id | pharmacy_id = str(current_user["pharmacy_id"]) |
| main.py | 514 | pharmacy_id | FROM medicines m WHERE m.pharmacy_id = :pid |
| main.py | 535 | pharmacy_id | WHERE m.pharmacy_id = :pid AND b.is_active = true |
| main.py | 535 | is_active | WHERE m.pharmacy_id = :pid AND b.is_active = true |
| medicines.py | 60 | is_active | Batch.is_active == True |
| medicines.py | 278 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 289 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| medicines.py | 337 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 379 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 412 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 439 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 449 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"], |
| medicines.py | 516 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| medicines.py | 547 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| medicines.py | 578 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| medicines.py | 612 | pharmacy_id | Medicine.pharmacy_id == current_user["pharmacy_id"] |
| models.py | 572 | is_active | is_active = Column(Boolean, default=False) |
| models.py | 589 | user insert | class User(Base): |
| models.py | 594 | pharmacy_id | pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False) |
| models.py | 595 | username | username = Column(String(50), unique=True, nullable=False) |
| models.py | 596 | password_hash | password_hash = Column(String(255), nullable=False) |
| models.py | 597 | role | role = Column(String(20), nullable=False)  # Legacy: 'admin' or 'employee' (kept for compatibility) |
| models.py | 598 | role_id | role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)  # New RBAC |
| models.py | 601 | is_active | is_active = Column(Boolean, default=True) |
| models.py | 648 | role_id | role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True) |
| models.py | 657 | pharmacy_id | pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False) |
| models.py | 702 | is_active | is_active = Column(Boolean, default=True) |
| models.py | 714 | pharmacy_id | pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False) |
| rbac_seeder.py | 57 | role | role = Role(name=name, display_name=display_name, description=description) |
| rbac_seeder.py | 77 | role | role = roles[role_name] |
| rbac_seeder.py | 81 | role_id | session.add(RolePermission(role_id=key[0], permission_id=key[1])) |
| rbac_seeder.py | 87 | role | user.role_id = roles["owner"].id if user.role == "admin" else roles["cashier"].id |
| rbac_seeder.py | 87 | role_id | user.role_id = roles["owner"].id if user.role == "admin" else roles["cashier"].id |
| reports.py | 96 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| reports.py | 104 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 120 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 135 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 159 | is_active | WHERE is_active = true AND quantity > 0 AND expiry_date > NOW() |
| reports.py | 162 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| reports.py | 173 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| reports.py | 174 | is_active | AND b.is_active = true |
| reports.py | 188 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| reports.py | 189 | is_active | AND b.is_active = true |
| reports.py | 206 | is_active | WHERE is_active = true AND quantity > 0 AND expiry_date > NOW() |
| reports.py | 209 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| reports.py | 255 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 322 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| reports.py | 340 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 447 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| reports.py | 469 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 501 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 542 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| reports.py | 552 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 562 | is_active | WHERE b.is_active = true |
| reports.py | 581 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| reports.py | 642 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| reports.py | 656 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| reports.py | 665 | is_active | WHERE is_active = true |
| reports.py | 688 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| routers\user_context.py | 35 | role_id | role_id = user.get("role_id") or "" |
| sales.py | 49 | pharmacy_id | text("SELECT COALESCE(MAX(invoice_number), 0) + 1 FROM sales WHERE pharmacy_id = :pid"), |
| sales.py | 98 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 118 | pharmacy_id | AND m.pharmacy_id = :pid |
| sales.py | 119 | is_active | AND b.is_active = true |
| sales.py | 164 | pharmacy_id | pharmacy_id=uuid.UUID(pharmacy_id), |
| sales.py | 184 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(pharmacy_id) |
| sales.py | 202 | pharmacy_id | pharmacy_id=pharmacy_id, |
| sales.py | 243 | is_active | batch.is_active = False |
| sales.py | 305 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 315 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| sales.py | 317 | pharmacy_id | count_query = "SELECT COUNT(*) FROM sales s WHERE s.pharmacy_id = :pid" |
| sales.py | 408 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 418 | pharmacy_id | Sale.pharmacy_id == uuid.UUID(pharmacy_id) |
| sales.py | 488 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 493 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(pharmacy_id), |
| sales.py | 511 | is_active | AND is_active = true |
| sales.py | 572 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 583 | pharmacy_id | WHERE s.pharmacy_id = :pid |
| sales.py | 601 | pharmacy_id | WHERE m.pharmacy_id = :pid |
| sales.py | 605 | is_active | AND b.is_active = true |
| sales.py | 640 | pharmacy_id | pharmacy_id = current_user["pharmacy_id"] |
| sales.py | 643 | pharmacy_id | Medicine.pharmacy_id == uuid.UUID(pharmacy_id), |
| sales.py | 656 | is_active | AND is_active = true |
| schema.sql | 116 | is_active | CREATE INDEX IF NOT EXISTS idx_batches_active ON batches(is_active) WHERE is_active = true; |
| scripts\bootstrap_marketing_demo.py | 55 | is_active | owner_name=args.owner_name, is_active=True, type="demo", |
| scripts\bootstrap_marketing_demo.py | 61 | username | user = db.query(User).filter(User.username == args.username).first() |
| scripts\bootstrap_marketing_demo.py | 72 | user insert | user = User( |
| scripts\bootstrap_marketing_demo.py | 73 | username | id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=args.username, |
| scripts\bootstrap_marketing_demo.py | 73 | pharmacy_id | id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=args.username, |
| scripts\bootstrap_marketing_demo.py | 74 | password_hash | full_name=args.owner_name, password_hash=get_password_hash(password), |
| scripts\bootstrap_marketing_demo.py | 75 | role | role="admin", role_id=owner_role.id, is_active=True, |
| scripts\bootstrap_marketing_demo.py | 75 | role_id | role="admin", role_id=owner_role.id, is_active=True, |
| scripts\bootstrap_marketing_demo.py | 75 | is_active | role="admin", role_id=owner_role.id, is_active=True, |
| scripts\bootstrap_marketing_demo.py | 96 | pharmacy_id | pharmacy_id = str(pharmacy.id) |
| settings.py | 61 | pharmacy_id | User.pharmacy_id == ph_id |
| settings.py | 85 | username | existing = db.query(User).filter(User.username == data.username).first() |
| settings.py | 94 | role | role_name = "owner" if data.role == "admin" else "cashier" |
| settings.py | 96 | user insert | new_user = User( |
| settings.py | 98 | pharmacy_id | pharmacy_id=ph_id, |
| settings.py | 99 | username | username=data.username, |
| settings.py | 101 | password_hash | password_hash=get_password_hash(data.password), |
| settings.py | 102 | role | role=data.role, |
| settings.py | 103 | role_id | role_id=role_obj.id, |
| settings.py | 104 | is_active | is_active=True |
| settings.py | 114 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| settings.py | 155 | pharmacy_id | User.pharmacy_id == ph_id |
| settings.py | 161 | role | if employee.role == "admin" and employee.is_active: |
| settings.py | 163 | pharmacy_id | User.pharmacy_id == ph_id, |
| settings.py | 164 | role | User.role == "admin", |
| settings.py | 165 | is_active | User.is_active == True, |
| settings.py | 171 | user delete | db.delete(employee) |
| settings.py | 177 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| settings.py | 217 | pharmacy_id | User.pharmacy_id == ph_id |
| settings.py | 223 | role | if employee.role == "admin" and employee.is_active and not data.is_active: |
| settings.py | 225 | pharmacy_id | User.pharmacy_id == ph_id, |
| settings.py | 226 | role | User.role == "admin", |
| settings.py | 227 | is_active | User.is_active == True, |
| settings.py | 232 | is_active | employee.is_active = data.is_active |
| settings.py | 242 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| settings.py | 279 | password_hash | user.password_hash = get_password_hash(data.new_password) |
| settings.py | 284 | pharmacy_id | pharmacy_id=current_user["pharmacy_id"], |
| tests\test_release_security.py | 66 | username | def _create_demo_admin(session, username="demo_admin", password="OriginalPassword123!"): |
| tests\test_release_security.py | 68 | is_active | pharmacy = Pharmacy(id=uuid.uuid4(), product_key=f"DEMO-{uuid.uuid4().hex}", name="Demo", owner_name |
| tests\test_release_security.py | 70 | user insert | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | password_hash | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | username | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | pharmacy_id | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | role | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | role_id | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 70 | is_active | user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", pas |
| tests\test_release_security.py | 92 | is_active | pharmacy = Pharmacy(id=uuid.uuid4(), product_key="CUSTOMER-KEY-123", name="Customer", owner_name="Ow |
| tests\test_release_security.py | 107 | username | _, user = _create_demo_admin(session, username="owner") |
| tests\test_release_security.py | 123 | username | args = argparse.Namespace(confirm_demo_bootstrap=True, username="marketing_admin", demo_key="MARKETI |
| tests\test_release_security.py | 126 | username | user = check.query(User).filter(User.username == "marketing_admin").one() |
| tests\test_release_security.py | 130 | username | user = check.query(User).filter(User.username == "marketing_admin").one() |
| tests\test_release_security.py | 188 | user insert | assert "User(" not in startup_source |

## Automatic Execution

Production starts only `uvicorn main:app`. FastAPI lifespan calls `startup.initialize_database()`, which creates schema/RBAC metadata only. It does not import or invoke demo/test/maintenance scripts. No GitHub Actions, cron, Celery, APScheduler, or background worker configuration exists.

## External PostgreSQL Gate

`render.yaml` expects dashboard-supplied `DATABASE_URL`. Real Neon startup/integration remains an external gate until credentials are supplied.

## Local Validation Results

- `pytest -vv -p no:cacheprovider`: 13 passed, 1 skipped (real PostgreSQL gate).
- `py_compile`: 29 Python files passed.
- Production import: passed (79 registered FastAPI routes).
- YAML, secret, dangerous-operation, and route-security scans: passed locally.

## Certification Answers

| Question | Answer | Evidence |
|---|---|---|
| Anonymous user can delete/replace an administrator? | NO | JWT/admin authorization and last-admin guards. |
| Public endpoint can reset demo/customer data? | NO | Legacy validation endpoints return 404. |
| Production startup can create demo data? | NO | Lifespan performs schema/RBAC initialization only. |
| Deployment automatically runs a destructive seeder? | NO | Uvicorn only; no scheduler/CI seed hook. |
| Demo reseed can delete users? | NO | No User delete remains; repeat tested. |
| Demo reseed can change an existing hash? | NO | Existing users are skipped; tested. |
| Script can target production without confirmation? | NO | Legacy scripts fail closed; bootstrap requires confirmation. |
| Endpoint can change admin password without authentication? | NO | Current-password or admin authorization required. |
| Identity/role/ownership can change without authorization? | NO | No public mutation; onboarding requires product key. |
| Empty production PostgreSQL initializes securely? | NOT PROVEN | Real PostgreSQL gate is skipped. |
| Demo can initialize without public destructive endpoint? | YES | Confirmed CLI bootstrap. |
| Users/hashes survive real deploy and RBAC seeding? | NOT PROVEN | Local simulation passed; real PostgreSQL unavailable. |
| Safe to connect to external PostgreSQL? | NOT PROVEN | Configuration passed; Neon connectivity untested. |
| All destructive operations guarded and audited? | NO | Critical paths covered; request IP is not uniform in legacy mutations. |
| Ready for paid customer production? | NO | Real PostgreSQL and audit normalization remain. |

## Decision

**APPROVED FOR LOCAL VALIDATION**

Marketing demo deployment remains blocked by the Neon integration gate in `DEPLOYMENT_RUNBOOK.md`. No deployment or push was performed.
