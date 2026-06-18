"""RBAC Phase 1: roles, permissions, role_permissions, users.role_id

Revision ID: 20240618_rbac_phase1
Revises: 20240618_add_pharmacy_type
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '20240618_rbac_phase1'
down_revision = '20240618_add_pharmacy_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create roles table
    op.create_table(
        'roles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(30), unique=True, nullable=False),
        sa.Column('display_name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # 2. Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # 3. Create role_permissions table
    op.create_table(
        'role_permissions',
        sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', UUID(as_uuid=True), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    # 4. Seed roles
    roles_table = sa.table(
        'roles',
        sa.column('id', UUID(as_uuid=True)),
        sa.column('name', sa.String(30)),
        sa.column('display_name', sa.String(50)),
        sa.column('description', sa.Text),
    )

    role_ids = {}
    for name, display_name, desc in [
        ('owner', 'المالك', 'صاحب الصيدلية - صلاحيات كاملة'),
        ('manager', 'المدير', 'مدير العمليات - صلاحيات إدارية ومالية'),
        ('pharmacist', 'الصيدلي', 'صيدلي مرخص - صلاحيات مهنية'),
        ('cashier', 'الكاشير', 'محاسب / كاشير - نقطة البيع'),
        ('store_keeper', 'أمين المخزن', 'مسؤول المخزون - استلام وتعديل المخزون'),
    ]:
        role_id = uuid.uuid4()
        role_ids[name] = role_id
        op.bulk_insert(roles_table, [{
            'id': role_id,
            'name': name,
            'display_name': display_name,
            'description': desc,
        }])

    # 5. Seed permissions (24 permissions)
    permissions_table = sa.table(
        'permissions',
        sa.column('id', UUID(as_uuid=True)),
        sa.column('code', sa.String(50)),
        sa.column('category', sa.String(30)),
        sa.column('description', sa.Text),
    )

    perm_ids = {}
    for code, category, desc in [
        # Medicines
        ('medicines.view', 'medicines', 'عرض قائمة الأدوية والبحث'),
        ('medicines.create', 'medicines', 'إضافة دواء جديد'),
        ('medicines.edit', 'medicines', 'تعديل بيانات الدواء والسعر والمخزون'),
        ('medicines.delete', 'medicines', 'حذف دواء'),
        # Inventory
        ('inventory.view', 'inventory', 'عرض المخزون والدفعات'),
        ('inventory.receive', 'inventory', 'استلام دفعات جديدة'),
        ('inventory.adjust', 'inventory', 'الجرد وتعديل كميات المخزون'),
        ('inventory.view_expired', 'inventory', 'عرض الأصناف منتهية الصلاحية'),
        # Sales
        ('sales.pos', 'sales', 'إجراء عملية بيع في نقطة البيع'),
        ('sales.view_history', 'sales', 'عرض سجل المبيعات'),
        ('sales.void', 'sales', 'إلغاء / استرجاع مبيعة'),
        # Reports
        ('reports.sales', 'reports', 'تقرير المبيعات'),
        ('reports.slow_moving', 'reports', 'تقرير الأدوية الراكدة'),
        ('reports.forecast', 'reports', 'تقرير توقعات الشراء'),
        # Profit
        ('profit.view', 'profit', 'تقرير الأرباح والهوامش والتكاليف'),
        # Employees
        ('employees.view', 'employees', 'عرض قائمة الموظفين'),
        ('employees.manage', 'employees', 'إضافة وتعديل وحذف وتفعيل/تعطيل موظفين'),
        # Settings
        ('settings.view', 'settings', 'عرض إعدادات الصيدلية والإيصال'),
        ('settings.manage', 'settings', 'إدارة العملة والإعدادات المتقدمة'),
        # Purchase
        ('purchase.view', 'purchase', 'عرض الموردين وأوامر الشراء'),
    ]:
        perm_id = uuid.uuid4()
        perm_ids[code] = perm_id
        op.bulk_insert(permissions_table, [{
            'id': perm_id,
            'code': code,
            'category': category,
            'description': desc,
        }])

    # 6. Seed role_permissions mapping
    role_perms_table = sa.table(
        'role_permissions',
        sa.column('role_id', UUID(as_uuid=True)),
        sa.column('permission_id', UUID(as_uuid=True)),
    )

    # Permission mapping per role
    role_perm_map = {
        'owner': [
            'medicines.view', 'medicines.create', 'medicines.edit', 'medicines.delete',
            'inventory.view', 'inventory.receive', 'inventory.adjust', 'inventory.view_expired',
            'sales.pos', 'sales.view_history', 'sales.void',
            'reports.sales', 'reports.slow_moving', 'reports.forecast',
            'profit.view',
            'employees.view', 'employees.manage',
            'settings.view', 'settings.manage',
            'purchase.view',
        ],
        'manager': [
            'medicines.view', 'medicines.create', 'medicines.edit',
            'inventory.view', 'inventory.receive', 'inventory.adjust', 'inventory.view_expired',
            'sales.pos', 'sales.view_history', 'sales.void',
            'reports.sales', 'reports.slow_moving', 'reports.forecast',
            'profit.view',
            'employees.view', 'employees.manage',
            'settings.view',
            'purchase.view',
        ],
        'pharmacist': [
            'medicines.view', 'medicines.create', 'medicines.edit',
            'inventory.view', 'inventory.receive', 'inventory.adjust', 'inventory.view_expired',
            'sales.pos', 'sales.view_history', 'sales.void',
            'reports.sales', 'reports.slow_moving', 'reports.forecast',
            'purchase.view',
        ],
        'cashier': [
            'medicines.view',
            'inventory.view', 'inventory.view_expired',
            'sales.pos',
        ],
        'store_keeper': [
            'medicines.view',
            'inventory.view', 'inventory.receive', 'inventory.adjust', 'inventory.view_expired',
            'reports.forecast',
            'purchase.view',
        ],
    }

    for role_name, perm_codes in role_perm_map.items():
        for perm_code in perm_codes:
            op.bulk_insert(role_perms_table, [{
                'role_id': role_ids[role_name],
                'permission_id': perm_ids[perm_code],
            }])

    # 7. Add role_id column to users (nullable initially)
    op.add_column('users', sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('roles.id'), nullable=True))

    # 8. Backfill role_id from existing role column
    # admin -> owner, employee -> cashier
    op.execute(
        sa.text("""
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = 'owner')
            WHERE role = 'admin'
        """)
    )
    op.execute(
        sa.text("""
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = 'cashier')
            WHERE role = 'employee'
        """)
    )

    # 9. Ensure all users have role_id (fallback for any unexpected values)
    op.execute(
        sa.text("""
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = 'cashier')
            WHERE role_id IS NULL
        """)
    )

    # 10. Make role_id NOT NULL
    op.alter_column('users', 'role_id', nullable=False)


def downgrade() -> None:
    # Reverse: drop role_id, drop tables
    op.drop_column('users', 'role_id')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('roles')