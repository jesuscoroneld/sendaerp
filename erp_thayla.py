
"""
╔══════════════════════════════════════════════════════════════╗
║         SENDA ERP — Sistema de Gestión Empresarial          ║
║         Flask + React (single-file) + SQLite → MongoDB      ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, get_jwt
)
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
import json, os, uuid

# ─── App Setup ───────────────────────────────────────────────
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///senda_erp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'senda-erp-secret-2025-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'flask-secret-2025')

db     = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt    = JWTManager(app)
CORS(app, origins="*")


# ─────────────────────────────────────────────────────────────
# MODELOS / DATABASE
# ─────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id          = db.Column(db.Integer, primary_key=True)
    uuid        = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    username    = db.Column(db.String(80), unique=True, nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False)
    password    = db.Column(db.String(200), nullable=False)
    full_name   = db.Column(db.String(150), nullable=False)
    role        = db.Column(db.String(20), default='viewer')  # admin | editor | viewer
    department  = db.Column(db.String(80))
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    last_login  = db.Column(db.DateTime)

    def to_dict(self, include_sensitive=False):
        d = {
            'id': self.id, 'uuid': self.uuid,
            'username': self.username, 'email': self.email,
            'full_name': self.full_name, 'role': self.role,
            'department': self.department, 'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        return d


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    username    = db.Column(db.String(80))
    action      = db.Column(db.String(200), nullable=False)
    module      = db.Column(db.String(50))
    record_id   = db.Column(db.String(50))
    old_values  = db.Column(db.Text)
    new_values  = db.Column(db.Text)
    ip_address  = db.Column(db.String(50))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username,
            'action': self.action, 'module': self.module,
            'record_id': self.record_id,
            'old_values': json.loads(self.old_values) if self.old_values else None,
            'new_values': json.loads(self.new_values) if self.new_values else None,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat(),
        }


# ── Inventario ──────────────────────────────────────────────
class InventoryItem(db.Model):
    __tablename__ = 'inventory'
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(50), unique=True, nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    category    = db.Column(db.String(80))
    unit        = db.Column(db.String(30))
    quantity    = db.Column(db.Float, default=0)
    min_stock   = db.Column(db.Float, default=0)
    cost_price  = db.Column(db.Float, default=0)
    sale_price  = db.Column(db.Float, default=0)
    supplier    = db.Column(db.String(150))
    location    = db.Column(db.String(100))
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'code': self.code, 'name': self.name,
            'category': self.category, 'unit': self.unit,
            'quantity': self.quantity, 'min_stock': self.min_stock,
            'cost_price': self.cost_price, 'sale_price': self.sale_price,
            'supplier': self.supplier, 'location': self.location,
            'is_active': self.is_active,
            'status': 'low' if self.quantity <= self.min_stock else 'ok',
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Planilla de Pagos ────────────────────────────────────────
class PayrollRecord(db.Model):
    __tablename__ = 'payroll'
    id              = db.Column(db.Integer, primary_key=True)
    employee_name   = db.Column(db.String(150), nullable=False)
    employee_id_num = db.Column(db.String(50))
    department      = db.Column(db.String(80))
    position        = db.Column(db.String(100))
    base_salary     = db.Column(db.Float, default=0)
    bonus           = db.Column(db.Float, default=0)
    overtime        = db.Column(db.Float, default=0)
    deductions      = db.Column(db.Float, default=0)
    ips             = db.Column(db.Float, default=0)
    net_salary      = db.Column(db.Float, default=0)
    period_month    = db.Column(db.Integer)
    period_year     = db.Column(db.Integer)
    status          = db.Column(db.String(20), default='pending')  # pending|paid|cancelled
    payment_date    = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'employee_name': self.employee_name,
            'employee_id_num': self.employee_id_num,
            'department': self.department, 'position': self.position,
            'base_salary': self.base_salary, 'bonus': self.bonus,
            'overtime': self.overtime, 'deductions': self.deductions,
            'ips': self.ips, 'net_salary': self.net_salary,
            'period_month': self.period_month, 'period_year': self.period_year,
            'status': self.status,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'created_at': self.created_at.isoformat(),
        }


# ── Producción ───────────────────────────────────────────────
class ProductionOrder(db.Model):
    __tablename__ = 'production'
    id              = db.Column(db.Integer, primary_key=True)
    order_number    = db.Column(db.String(50), unique=True)
    product_name    = db.Column(db.String(150), nullable=False)
    quantity_planned= db.Column(db.Float, default=0)
    quantity_done   = db.Column(db.Float, default=0)
    unit            = db.Column(db.String(30))
    start_date      = db.Column(db.DateTime)
    end_date        = db.Column(db.DateTime)
    status          = db.Column(db.String(20), default='draft')  # draft|in_progress|done|cancelled
    responsible     = db.Column(db.String(100))
    notes           = db.Column(db.Text)
    cost_materials  = db.Column(db.Float, default=0)
    cost_labor      = db.Column(db.Float, default=0)
    cost_overhead   = db.Column(db.Float, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        progress = round((self.quantity_done / self.quantity_planned * 100) if self.quantity_planned else 0, 1)
        return {
            'id': self.id, 'order_number': self.order_number,
            'product_name': self.product_name,
            'quantity_planned': self.quantity_planned,
            'quantity_done': self.quantity_done,
            'unit': self.unit,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status, 'responsible': self.responsible,
            'notes': self.notes,
            'cost_materials': self.cost_materials,
            'cost_labor': self.cost_labor,
            'cost_overhead': self.cost_overhead,
            'total_cost': self.cost_materials + self.cost_labor + self.cost_overhead,
            'progress': progress,
            'created_at': self.created_at.isoformat(),
        }


# ── Finanzas ─────────────────────────────────────────────────
class FinanceTransaction(db.Model):
    __tablename__ = 'finance'
    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(20), nullable=False)  # income|expense|transfer
    category    = db.Column(db.String(80))
    description = db.Column(db.String(200), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    currency    = db.Column(db.String(10), default='PYG')
    account     = db.Column(db.String(100))
    reference   = db.Column(db.String(100))
    date        = db.Column(db.DateTime, default=datetime.utcnow)
    status      = db.Column(db.String(20), default='confirmed')
    created_by  = db.Column(db.String(80))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'type': self.type, 'category': self.category,
            'description': self.description, 'amount': self.amount,
            'currency': self.currency, 'account': self.account,
            'reference': self.reference,
            'date': self.date.isoformat() if self.date else None,
            'status': self.status, 'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
        }


# ── Contabilidad ─────────────────────────────────────────────
class AccountingEntry(db.Model):
    __tablename__ = 'accounting'
    id          = db.Column(db.Integer, primary_key=True)
    entry_number= db.Column(db.String(50), unique=True)
    date        = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))
    account_code= db.Column(db.String(20))
    account_name= db.Column(db.String(100))
    debit       = db.Column(db.Float, default=0)
    credit      = db.Column(db.Float, default=0)
    reference   = db.Column(db.String(100))
    period      = db.Column(db.String(20))
    is_closed   = db.Column(db.Boolean, default=False)
    created_by  = db.Column(db.String(80))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'entry_number': self.entry_number,
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'account_code': self.account_code, 'account_name': self.account_name,
            'debit': self.debit, 'credit': self.credit,
            'reference': self.reference, 'period': self.period,
            'is_closed': self.is_closed, 'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def log_action(user_id, username, action, module, record_id=None, old=None, new=None):
    log = AuditLog(
        user_id=user_id, username=username, action=action,
        module=module, record_id=str(record_id) if record_id else None,
        old_values=json.dumps(old) if old else None,
        new_values=json.dumps(new) if new else None,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        user = User.query.get(identity)
        if not user or user.role != 'admin':
            return jsonify({'error': 'Se requiere rol de administrador'}), 403
        return fn(*args, **kwargs)
    return wrapper


def editor_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        user = User.query.get(identity)
        if not user or user.role not in ('admin', 'editor'):
            return jsonify({'error': 'Se requiere rol de editor o admin'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# RUTAS AUTH
# ─────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if not user or not bcrypt.check_password_hash(user.password, data.get('password', '')):
        return jsonify({'error': 'Credenciales incorrectas'}), 401
    if not user.is_active:
        return jsonify({'error': 'Usuario desactivado. Contacte al administrador'}), 403
    user.last_login = datetime.utcnow()
    db.session.commit()
    token = create_access_token(identity=user.id, additional_claims={'role': user.role})
    log_action(user.id, user.username, 'LOGIN', 'auth')
    return jsonify({
        'token': token,
        'user': user.to_dict(),
        'message': f'Bienvenido, {user.full_name}'
    })


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get(get_jwt_identity())
    return jsonify(user.to_dict())


@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user = User.query.get(get_jwt_identity())
    data = request.get_json()
    if not bcrypt.check_password_hash(user.password, data.get('current_password', '')):
        return jsonify({'error': 'Contraseña actual incorrecta'}), 400
    user.password = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
    db.session.commit()
    log_action(user.id, user.username, 'CHANGE_PASSWORD', 'auth')
    return jsonify({'message': 'Contraseña actualizada correctamente'})


# ─────────────────────────────────────────────────────────────
# RUTAS USUARIOS (solo admin)
# ─────────────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    current_user = User.query.get(get_jwt_identity())
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Nombre de usuario ya existe'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email ya registrado'}), 400
    hashed = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(
        username=data['username'], email=data['email'],
        password=hashed, full_name=data['full_name'],
        role=data.get('role', 'viewer'),
        department=data.get('department', '')
    )
    db.session.add(user)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE_USER', 'users',
               record_id=user.id, new=user.to_dict())
    return jsonify({'message': 'Usuario creado', 'user': user.to_dict()}), 201


@app.route('/api/users/<int:uid>', methods=['PUT'])
@admin_required
def update_user(uid):
    current_user = User.query.get(get_jwt_identity())
    user = User.query.get_or_404(uid)
    old = user.to_dict()
    data = request.get_json()
    for field in ('full_name', 'email', 'role', 'department', 'is_active'):
        if field in data:
            setattr(user, field, data[field])
    if 'password' in data and data['password']:
        user.password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE_USER', 'users',
               record_id=uid, old=old, new=user.to_dict())
    return jsonify({'message': 'Usuario actualizado', 'user': user.to_dict()})


@app.route('/api/users/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    current_user = User.query.get(get_jwt_identity())
    if uid == current_user.id:
        return jsonify({'error': 'No puede eliminarse a sí mismo'}), 400
    user = User.query.get_or_404(uid)
    old = user.to_dict()
    db.session.delete(user)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE_USER', 'users',
               record_id=uid, old=old)
    return jsonify({'message': 'Usuario eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS AUDIT LOG (solo admin)
# ─────────────────────────────────────────────────────────────

@app.route('/api/audit', methods=['GET'])
@admin_required
def get_audit():
    module = request.args.get('module')
    limit  = int(request.args.get('limit', 100))
    q = AuditLog.query.order_by(AuditLog.created_at.desc())
    if module:
        q = q.filter_by(module=module)
    logs = q.limit(limit).all()
    return jsonify([l.to_dict() for l in logs])


# ─────────────────────────────────────────────────────────────
# RUTAS INVENTARIO
# ─────────────────────────────────────────────────────────────

@app.route('/api/inventory', methods=['GET'])
@jwt_required()
def get_inventory():
    items = InventoryItem.query.filter_by(is_active=True).all()
    return jsonify([i.to_dict() for i in items])


@app.route('/api/inventory', methods=['POST'])
@editor_required
def create_inventory():
    current_user = User.query.get(get_jwt_identity())
    data = request.get_json()
    item = InventoryItem(**{k: v for k, v in data.items() if k != 'id'})
    db.session.add(item)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE', 'inventory',
               record_id=item.id, new=item.to_dict())
    return jsonify(item.to_dict()), 201


@app.route('/api/inventory/<int:iid>', methods=['PUT'])
@editor_required
def update_inventory(iid):
    current_user = User.query.get(get_jwt_identity())
    item = InventoryItem.query.get_or_404(iid)
    old = item.to_dict()
    data = request.get_json()
    for k, v in data.items():
        if hasattr(item, k) and k not in ('id', 'created_at'):
            setattr(item, k, v)
    item.updated_at = datetime.utcnow()
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE', 'inventory',
               record_id=iid, old=old, new=item.to_dict())
    return jsonify(item.to_dict())


@app.route('/api/inventory/<int:iid>', methods=['DELETE'])
@editor_required
def delete_inventory(iid):
    current_user = User.query.get(get_jwt_identity())
    item = InventoryItem.query.get_or_404(iid)
    old = item.to_dict()
    item.is_active = False
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE', 'inventory',
               record_id=iid, old=old)
    return jsonify({'message': 'Eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS PLANILLA DE PAGOS
# ─────────────────────────────────────────────────────────────

@app.route('/api/payroll', methods=['GET'])
@jwt_required()
def get_payroll():
    records = PayrollRecord.query.order_by(PayrollRecord.created_at.desc()).all()
    return jsonify([r.to_dict() for r in records])


@app.route('/api/payroll', methods=['POST'])
@editor_required
def create_payroll():
    current_user = User.query.get(get_jwt_identity())
    data = request.get_json()
    net = (data.get('base_salary', 0) + data.get('bonus', 0) + data.get('overtime', 0)
           - data.get('deductions', 0) - data.get('ips', 0))
    rec = PayrollRecord(
        employee_name=data['employee_name'],
        employee_id_num=data.get('employee_id_num', ''),
        department=data.get('department', ''),
        position=data.get('position', ''),
        base_salary=data.get('base_salary', 0),
        bonus=data.get('bonus', 0),
        overtime=data.get('overtime', 0),
        deductions=data.get('deductions', 0),
        ips=data.get('ips', 0),
        net_salary=net,
        period_month=data.get('period_month', datetime.utcnow().month),
        period_year=data.get('period_year', datetime.utcnow().year),
    )
    db.session.add(rec)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE', 'payroll',
               record_id=rec.id, new=rec.to_dict())
    return jsonify(rec.to_dict()), 201


@app.route('/api/payroll/<int:rid>', methods=['PUT'])
@editor_required
def update_payroll(rid):
    current_user = User.query.get(get_jwt_identity())
    rec = PayrollRecord.query.get_or_404(rid)
    old = rec.to_dict()
    data = request.get_json()
    for k, v in data.items():
        if hasattr(rec, k) and k not in ('id', 'created_at'):
            setattr(rec, k, v)
    rec.net_salary = (rec.base_salary + rec.bonus + rec.overtime
                      - rec.deductions - rec.ips)
    if data.get('status') == 'paid' and not rec.payment_date:
        rec.payment_date = datetime.utcnow()
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE', 'payroll',
               record_id=rid, old=old, new=rec.to_dict())
    return jsonify(rec.to_dict())


@app.route('/api/payroll/<int:rid>', methods=['DELETE'])
@editor_required
def delete_payroll(rid):
    current_user = User.query.get(get_jwt_identity())
    rec = PayrollRecord.query.get_or_404(rid)
    old = rec.to_dict()
    db.session.delete(rec)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE', 'payroll',
               record_id=rid, old=old)
    return jsonify({'message': 'Eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS PRODUCCIÓN
# ─────────────────────────────────────────────────────────────

@app.route('/api/production', methods=['GET'])
@jwt_required()
def get_production():
    orders = ProductionOrder.query.order_by(ProductionOrder.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route('/api/production', methods=['POST'])
@editor_required
def create_production():
    current_user = User.query.get(get_jwt_identity())
    data = request.get_json()
    num = f"OP-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    order = ProductionOrder(
        order_number=num,
        product_name=data['product_name'],
        quantity_planned=data.get('quantity_planned', 0),
        quantity_done=data.get('quantity_done', 0),
        unit=data.get('unit', 'unidad'),
        start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
        end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
        status=data.get('status', 'draft'),
        responsible=data.get('responsible', ''),
        notes=data.get('notes', ''),
        cost_materials=data.get('cost_materials', 0),
        cost_labor=data.get('cost_labor', 0),
        cost_overhead=data.get('cost_overhead', 0),
    )
    db.session.add(order)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE', 'production',
               record_id=order.id, new=order.to_dict())
    return jsonify(order.to_dict()), 201


@app.route('/api/production/<int:oid>', methods=['PUT'])
@editor_required
def update_production(oid):
    current_user = User.query.get(get_jwt_identity())
    order = ProductionOrder.query.get_or_404(oid)
    old = order.to_dict()
    data = request.get_json()
    for k, v in data.items():
        if hasattr(order, k) and k not in ('id', 'created_at', 'order_number'):
            if k in ('start_date', 'end_date') and v:
                setattr(order, k, datetime.fromisoformat(v))
            else:
                setattr(order, k, v)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE', 'production',
               record_id=oid, old=old, new=order.to_dict())
    return jsonify(order.to_dict())


@app.route('/api/production/<int:oid>', methods=['DELETE'])
@editor_required
def delete_production(oid):
    current_user = User.query.get(get_jwt_identity())
    order = ProductionOrder.query.get_or_404(oid)
    old = order.to_dict()
    db.session.delete(order)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE', 'production',
               record_id=oid, old=old)
    return jsonify({'message': 'Eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS FINANZAS
# ─────────────────────────────────────────────────────────────

@app.route('/api/finance', methods=['GET'])
@jwt_required()
def get_finance():
    txs = FinanceTransaction.query.order_by(FinanceTransaction.date.desc()).all()
    return jsonify([t.to_dict() for t in txs])


@app.route('/api/finance', methods=['POST'])
@editor_required
def create_finance():
    current_user = User.query.get(get_jwt_identity())
    data = request.get_json()
    tx = FinanceTransaction(
        type=data['type'], category=data.get('category', ''),
        description=data['description'], amount=data['amount'],
        currency=data.get('currency', 'PYG'),
        account=data.get('account', ''),
        reference=data.get('reference', ''),
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.utcnow(),
        created_by=current_user.username
    )
    db.session.add(tx)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE', 'finance',
               record_id=tx.id, new=tx.to_dict())
    return jsonify(tx.to_dict()), 201


@app.route('/api/finance/<int:tid>', methods=['PUT'])
@editor_required
def update_finance(tid):
    current_user = User.query.get(get_jwt_identity())
    tx = FinanceTransaction.query.get_or_404(tid)
    old = tx.to_dict()
    data = request.get_json()
    for k, v in data.items():
        if hasattr(tx, k) and k not in ('id', 'created_at', 'created_by'):
            if k == 'date' and v:
                setattr(tx, k, datetime.fromisoformat(v))
            else:
                setattr(tx, k, v)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE', 'finance',
               record_id=tid, old=old, new=tx.to_dict())
    return jsonify(tx.to_dict())


@app.route('/api/finance/<int:tid>', methods=['DELETE'])
@editor_required
def delete_finance(tid):
    current_user = User.query.get(get_jwt_identity())
    tx = FinanceTransaction.query.get_or_404(tid)
    old = tx.to_dict()
    db.session.delete(tx)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE', 'finance',
               record_id=tid, old=old)
    return jsonify({'message': 'Eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS CONTABILIDAD
# ─────────────────────────────────────────────────────────────

@app.route('/api/accounting', methods=['GET'])
@jwt_required()
def get_accounting():
    entries = AccountingEntry.query.order_by(AccountingEntry.date.desc()).all()
    return jsonify([e.to_dict() for e in entries])


@app.route('/api/accounting', methods=['POST'])
@editor_required
def create_accounting():
    current_user = User.query.get(get_jwt_identity())
    data = request.get_json()
    num = f"AST-{datetime.utcnow().strftime('%Y%m')}-{str(uuid.uuid4())[:6].upper()}"
    entry = AccountingEntry(
        entry_number=num,
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.utcnow(),
        description=data.get('description', ''),
        account_code=data.get('account_code', ''),
        account_name=data.get('account_name', ''),
        debit=data.get('debit', 0),
        credit=data.get('credit', 0),
        reference=data.get('reference', ''),
        period=data.get('period', datetime.utcnow().strftime('%Y-%m')),
        created_by=current_user.username
    )
    db.session.add(entry)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'CREATE', 'accounting',
               record_id=entry.id, new=entry.to_dict())
    return jsonify(entry.to_dict()), 201


@app.route('/api/accounting/<int:eid>', methods=['PUT'])
@editor_required
def update_accounting(eid):
    current_user = User.query.get(get_jwt_identity())
    entry = AccountingEntry.query.get_or_404(eid)
    old = entry.to_dict()
    data = request.get_json()
    for k, v in data.items():
        if hasattr(entry, k) and k not in ('id', 'created_at', 'entry_number', 'created_by'):
            if k == 'date' and v:
                setattr(entry, k, datetime.fromisoformat(v))
            else:
                setattr(entry, k, v)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'UPDATE', 'accounting',
               record_id=eid, old=old, new=entry.to_dict())
    return jsonify(entry.to_dict())


@app.route('/api/accounting/<int:eid>', methods=['DELETE'])
@editor_required
def delete_accounting(eid):
    current_user = User.query.get(get_jwt_identity())
    entry = AccountingEntry.query.get_or_404(eid)
    old = entry.to_dict()
    db.session.delete(entry)
    db.session.commit()
    log_action(current_user.id, current_user.username, 'DELETE', 'accounting',
               record_id=eid, old=old)
    return jsonify({'message': 'Eliminado'})


# ─────────────────────────────────────────────────────────────
# RUTAS BI / DASHBOARD
# ─────────────────────────────────────────────────────────────

@app.route('/api/bi/summary', methods=['GET'])
@jwt_required()
def bi_summary():
    # Inventario
    items = InventoryItem.query.filter_by(is_active=True).all()
    inv_total_value = sum(i.quantity * i.cost_price for i in items)
    inv_low_stock   = sum(1 for i in items if i.quantity <= i.min_stock)

    # Finanzas del mes
    now = datetime.utcnow()
    month_txs = FinanceTransaction.query.filter(
        db.extract('month', FinanceTransaction.date) == now.month,
        db.extract('year',  FinanceTransaction.date) == now.year
    ).all()
    income   = sum(t.amount for t in month_txs if t.type == 'income')
    expenses = sum(t.amount for t in month_txs if t.type == 'expense')

    # Planilla del mes
    payroll_month = PayrollRecord.query.filter_by(
        period_month=now.month, period_year=now.year
    ).all()
    payroll_total = sum(r.net_salary for r in payroll_month)

    # Producción
    prod_orders = ProductionOrder.query.all()
    prod_in_progress = sum(1 for o in prod_orders if o.status == 'in_progress')
    prod_done = sum(1 for o in prod_orders if o.status == 'done')

    # Finanzas por mes (últimos 6)
    finance_trend = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12; y -= 1
        txs = FinanceTransaction.query.filter(
            db.extract('month', FinanceTransaction.date) == m,
            db.extract('year',  FinanceTransaction.date) == y
        ).all()
        finance_trend.append({
            'month': f"{y}-{m:02d}",
            'income': sum(t.amount for t in txs if t.type == 'income'),
            'expenses': sum(t.amount for t in txs if t.type == 'expense'),
        })

    # Inventario por categoría
    from collections import defaultdict
    cat_map = defaultdict(float)
    for item in items:
        cat_map[item.category or 'Sin categoría'] += item.quantity * item.cost_price
    inv_by_cat = [{'category': k, 'value': v} for k, v in cat_map.items()]

    # Contabilidad — balance
    entries = AccountingEntry.query.all()
    total_debit  = sum(e.debit for e in entries)
    total_credit = sum(e.credit for e in entries)

    return jsonify({
        'inventory': {
            'total_items': len(items),
            'total_value': inv_total_value,
            'low_stock_count': inv_low_stock,
            'by_category': inv_by_cat,
        },
        'finance': {
            'month_income': income,
            'month_expenses': expenses,
            'month_profit': income - expenses,
            'trend': finance_trend,
        },
        'payroll': {
            'month_total': payroll_total,
            'employee_count': len(payroll_month),
        },
        'production': {
            'total_orders': len(prod_orders),
            'in_progress': prod_in_progress,
            'completed': prod_done,
        },
        'accounting': {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'balance': total_debit - total_credit,
        }
    })


# ─────────────────────────────────────────────────────────────
# FRONTEND — HTML + REACT (single file)
# ─────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Senda ERP — Sistema de Gestión</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#0a0b0f;--surface:#12141a;--surface2:#1a1d26;--surface3:#22263a;
  --border:#2a2d3e;--border2:#353a50;
  --accent:#6c63ff;--accent2:#8b83ff;--accent-glow:rgba(108,99,255,.18);
  --green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6;--orange:#f97316;
  --text:#e8eaf2;--text2:#9aa0bc;--text3:#5a607a;
  --font-head:'Syne',sans-serif;--font-body:'DM Sans',sans-serif;--font-mono:'DM Mono',monospace;
  --radius:12px;--radius-sm:8px;--radius-lg:18px;
  --shadow:0 4px 24px rgba(0,0,0,.4);--shadow-lg:0 8px 48px rgba(0,0,0,.6);
  --sidebar:260px;--transition:.2s cubic-bezier(.4,0,.2,1);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body,#root{height:100%;background:var(--bg);color:var(--text);font-family:var(--font-body)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:10px}

/* ── LAYOUT ── */
.app{display:flex;height:100vh;overflow:hidden}
.sidebar{
  width:var(--sidebar);min-width:var(--sidebar);
  background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow:hidden;
  transition:width var(--transition),min-width var(--transition);
  z-index:100;
}
.sidebar.collapsed{width:68px;min-width:68px}
.sidebar-logo{
  padding:20px 18px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px;
}
.logo-mark{
  width:36px;height:36px;border-radius:10px;
  background:linear-gradient(135deg,var(--accent),#a855f7);
  display:flex;align-items:center;justify-content:center;
  font-family:var(--font-head);font-weight:800;font-size:16px;color:#fff;
  flex-shrink:0;box-shadow:0 0 20px var(--accent-glow);
}
.logo-text{font-family:var(--font-head);font-weight:700;font-size:17px;
  white-space:nowrap;overflow:hidden;
}
.logo-text span{color:var(--accent)}
.sidebar-nav{flex:1;overflow-y:auto;padding:12px 0}
.nav-section{padding:6px 16px 4px;font-size:10px;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--text3);
  white-space:nowrap;overflow:hidden;
}
.nav-item{
  display:flex;align-items:center;gap:12px;
  padding:10px 18px;cursor:pointer;border-radius:0;
  transition:background var(--transition),color var(--transition);
  position:relative;white-space:nowrap;
}
.nav-item:hover{background:var(--surface2)}
.nav-item.active{
  background:var(--accent-glow);color:var(--accent2);
}
.nav-item.active::before{
  content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:3px;height:60%;background:var(--accent);border-radius:0 3px 3px 0;
}
.nav-icon{font-size:18px;flex-shrink:0;width:22px;text-align:center}
.nav-label{font-size:13.5px;font-weight:500;overflow:hidden;text-overflow:ellipsis}
.sidebar-footer{padding:14px;border-top:1px solid var(--border)}
.user-card{
  display:flex;align-items:center;gap:10px;padding:10px;
  background:var(--surface2);border-radius:var(--radius-sm);cursor:pointer;
}
.avatar{
  width:34px;height:34px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),#a855f7);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:13px;flex-shrink:0;
}
.user-info{flex:1;overflow:hidden}
.user-name{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.user-role{font-size:11px;color:var(--text2);text-transform:capitalize}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{
  height:58px;padding:0 24px;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--border);background:var(--surface);
  gap:16px;flex-shrink:0;
}
.topbar-title{font-family:var(--font-head);font-weight:700;font-size:18px}
.topbar-actions{display:flex;align-items:center;gap:10px}
.content{flex:1;overflow-y:auto;padding:24px}

/* ── CARDS & GRIDS ── */
.grid{display:grid;gap:16px}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px;
}
.card-head{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:16px;
}
.card-title{font-family:var(--font-head);font-weight:700;font-size:15px}
.stat-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px;
  display:flex;flex-direction:column;gap:8px;
  transition:border-color var(--transition),transform var(--transition);
}
.stat-card:hover{border-color:var(--border2);transform:translateY(-2px)}
.stat-icon{
  width:40px;height:40px;border-radius:10px;
  display:flex;align-items:center;justify-content:center;font-size:18px;
}
.stat-value{font-family:var(--font-head);font-weight:800;font-size:26px}
.stat-label{font-size:12px;color:var(--text2);font-weight:500}
.stat-sub{font-size:12px;color:var(--text3)}

/* ── TABLE ── */
.table-wrap{overflow-x:auto;border-radius:var(--radius-sm)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{
  background:var(--surface2);padding:11px 14px;text-align:left;
  font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--text2);border-bottom:1px solid var(--border);white-space:nowrap;
}
td{
  padding:11px 14px;border-bottom:1px solid var(--border);
  color:var(--text);vertical-align:middle;
}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.02)}
.td-mono{font-family:var(--font-mono);font-size:12px}

/* ── BADGES ── */
.badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;
}
.badge-green{background:rgba(34,197,94,.15);color:var(--green)}
.badge-red{background:rgba(239,68,68,.15);color:var(--red)}
.badge-yellow{background:rgba(245,158,11,.15);color:var(--yellow)}
.badge-blue{background:rgba(59,130,246,.15);color:var(--blue)}
.badge-purple{background:rgba(108,99,255,.15);color:var(--accent2)}
.badge-gray{background:rgba(255,255,255,.08);color:var(--text2)}

/* ── BUTTONS ── */
.btn{
  display:inline-flex;align-items:center;gap:7px;
  padding:8px 16px;border-radius:var(--radius-sm);border:none;
  font-family:var(--font-body);font-size:13.5px;font-weight:600;
  cursor:pointer;transition:all var(--transition);white-space:nowrap;
}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2);box-shadow:0 4px 20px var(--accent-glow)}
.btn-secondary{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-secondary:hover{background:var(--surface3);border-color:var(--border2)}
.btn-danger{background:rgba(239,68,68,.15);color:var(--red);border:1px solid rgba(239,68,68,.3)}
.btn-danger:hover{background:rgba(239,68,68,.25)}
.btn-success{background:rgba(34,197,94,.15);color:var(--green);border:1px solid rgba(34,197,94,.3)}
.btn-success:hover{background:rgba(34,197,94,.25)}
.btn-sm{padding:5px 11px;font-size:12px}
.btn-icon{padding:7px;border-radius:var(--radius-sm)}

/* ── FORMS ── */
.form-group{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
label{font-size:12px;font-weight:600;color:var(--text2);letter-spacing:.05em;text-transform:uppercase}
input,select,textarea{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:var(--radius-sm);padding:9px 13px;
  color:var(--text);font-family:var(--font-body);font-size:14px;
  outline:none;transition:border-color var(--transition),box-shadow var(--transition);
  width:100%;
}
input:focus,select:focus,textarea:focus{
  border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow);
}
textarea{resize:vertical;min-height:80px}
select option{background:var(--surface2)}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.form-grid.g3{grid-template-columns:1fr 1fr 1fr}

/* ── MODAL ── */
.modal-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.7);
  display:flex;align-items:center;justify-content:center;z-index:1000;
  backdrop-filter:blur(4px);padding:20px;
}
.modal{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius-lg);padding:28px;
  width:100%;max-width:640px;max-height:90vh;overflow-y:auto;
  box-shadow:var(--shadow-lg);
}
.modal-title{font-family:var(--font-head);font-weight:700;font-size:20px;margin-bottom:22px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:22px;padding-top:18px;border-top:1px solid var(--border)}

/* ── LOGIN ── */
.login-page{
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:var(--bg);
  background-image:radial-gradient(ellipse at 20% 50%,rgba(108,99,255,.12) 0%,transparent 60%),
                   radial-gradient(ellipse at 80% 20%,rgba(168,85,247,.08) 0%,transparent 60%);
}
.login-card{
  width:100%;max-width:420px;padding:40px;
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);
}
.login-logo{text-align:center;margin-bottom:32px}
.login-logo .logo-mark{width:52px;height:52px;margin:0 auto 12px;font-size:22px}
.login-logo h1{font-family:var(--font-head);font-size:24px;font-weight:800}
.login-logo h1 span{color:var(--accent)}
.login-logo p{color:var(--text2);font-size:13px;margin-top:4px}

/* ── SEARCH ── */
.search-bar{
  display:flex;align-items:center;gap:8px;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:var(--radius-sm);padding:7px 12px;flex:1;max-width:300px;
}
.search-bar input{background:none;border:none;padding:0;font-size:13.5px}
.search-bar input:focus{box-shadow:none;border:none}

/* ── TOAST ── */
.toast-container{position:fixed;bottom:24px;right:24px;z-index:2000;display:flex;flex-direction:column;gap:8px}
.toast{
  padding:12px 18px;border-radius:var(--radius-sm);
  font-size:13.5px;font-weight:500;display:flex;align-items:center;gap:10px;
  animation:slideIn .3s ease;box-shadow:var(--shadow);
  min-width:240px;max-width:360px;
}
.toast-success{background:#14532d;border:1px solid #166534;color:#86efac}
.toast-error{background:#450a0a;border:1px solid #7f1d1d;color:#fca5a5}
.toast-info{background:#1e1b4b;border:1px solid #3730a3;color:#a5b4fc}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}

/* ── PROGRESS ── */
.progress-bar{height:6px;background:var(--border);border-radius:10px;overflow:hidden}
.progress-fill{height:100%;border-radius:10px;transition:width .5s ease}

/* ── KPI RING ── */
.kpi-ring{display:flex;align-items:center;gap:16px}

/* ── TABS ── */
.tabs{display:flex;gap:4px;background:var(--surface2);padding:4px;border-radius:var(--radius-sm);margin-bottom:20px}
.tab{
  padding:7px 16px;border-radius:6px;font-size:13px;font-weight:600;
  cursor:pointer;transition:all var(--transition);color:var(--text2);
}
.tab.active{background:var(--surface);color:var(--text);box-shadow:var(--shadow)}

/* ── CHIP ── */
.chip{
  display:inline-flex;align-items:center;gap:5px;
  padding:2px 9px;border-radius:20px;font-size:11px;
  background:var(--surface3);color:var(--text2);border:1px solid var(--border);
}

/* ── RESPONSIVE ── */
@media(max-width:1100px){
  .g4{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:768px){
  :root{--sidebar:0px}
  .sidebar{position:fixed;height:100%;transform:translateX(-260px);transition:transform var(--transition)}
  .sidebar.mobile-open{width:260px;min-width:260px;transform:translateX(0)}
  .sidebar.collapsed{width:260px}
  .g2,.g3,.g4{grid-template-columns:1fr}
  .form-grid{grid-template-columns:1fr}
  .content{padding:16px}
  .topbar{padding:0 16px}
  .modal{padding:20px}
}
@media(max-width:480px){
  .stat-value{font-size:20px}
  .topbar-title{font-size:15px}
}

/* ── MISC ── */
.text-accent{color:var(--accent)}
.text-green{color:var(--green)}
.text-red{color:var(--red)}
.text-yellow{color:var(--yellow)}
.text-muted{color:var(--text2)}
.divider{height:1px;background:var(--border);margin:16px 0}
.flex{display:flex}.items-center{align-items:center}.gap-2{gap:8px}.gap-3{gap:12px}
.ml-auto{margin-left:auto}.mt-4{margin-top:16px}.mb-4{margin-bottom:16px}
.font-head{font-family:var(--font-head)}.font-mono{font-family:var(--font-mono)}
.w-full{width:100%}.hidden{display:none!important}
.empty-state{text-align:center;padding:48px 20px;color:var(--text3)}
.empty-state h3{font-size:16px;margin-bottom:8px;color:var(--text2)}
.spin{animation:spin 1s linear infinite}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const {useState,useEffect,useCallback,useRef,createContext,useContext} = React;

/* ── API ────────────────────────────────────────────── */
const BASE = '';
const api = {
  async req(method, path, body){
    const token = localStorage.getItem('erp_token');
    const res = await fetch(BASE+path,{
      method, headers:{'Content-Type':'application/json',
        ...(token?{'Authorization':`Bearer ${token}`}:{})},
      body:body?JSON.stringify(body):undefined
    });
    const data = await res.json();
    if(!res.ok) throw new Error(data.error || 'Error del servidor');
    return data;
  },
  get:  (p)       => api.req('GET',p),
  post: (p,b)     => api.req('POST',p,b),
  put:  (p,b)     => api.req('PUT',p,b),
  del:  (p)       => api.req('DELETE',p),
};

/* ── CONTEXT ────────────────────────────────────────── */
const AppCtx = createContext(null);
const useApp = ()=>useContext(AppCtx);

/* ── TOAST ──────────────────────────────────────────── */
function ToastContainer({toasts}){
  return <div className="toast-container">{toasts.map(t=>(
    <div key={t.id} className={`toast toast-${t.type}`}>
      <span>{t.type==='success'?'✓':t.type==='error'?'✕':'ℹ'}</span>
      <span>{t.msg}</span>
    </div>
  ))}</div>;
}

/* ── FORMAT ──────────────────────────────────────────── */
const fmt={
  num:(n)=>new Intl.NumberFormat('es-PY').format(Math.round(n)),
  cur:(n,c='PYG')=>{
    if(c==='PYG') return `₲ ${fmt.num(n)}`;
    return new Intl.NumberFormat('es',{style:'currency',currency:c,maximumFractionDigits:0}).format(n);
  },
  date:(s)=>s?new Date(s).toLocaleDateString('es-PY',{day:'2-digit',month:'2-digit',year:'numeric'}):'—',
  pct:(n)=>n.toFixed(1)+'%',
};

/* ── STATUS BADGE ────────────────────────────────────── */
function StatusBadge({status}){
  const map={
    ok:{c:'badge-green',l:'Disponible'},low:{c:'badge-yellow',l:'Bajo Stock'},
    pending:{c:'badge-yellow',l:'Pendiente'},paid:{c:'badge-green',l:'Pagado'},
    cancelled:{c:'badge-red',l:'Cancelado'},
    draft:{c:'badge-gray',l:'Borrador'},in_progress:{c:'badge-blue',l:'En Curso'},
    done:{c:'badge-green',l:'Completado'},
    income:{c:'badge-green',l:'Ingreso'},expense:{c:'badge-red',l:'Egreso'},
    transfer:{c:'badge-blue',l:'Transferencia'},
    confirmed:{c:'badge-green',l:'Confirmado'},
    active:{c:'badge-green',l:'Activo'},inactive:{c:'badge-gray',l:'Inactivo'},
    admin:{c:'badge-purple',l:'Admin'},editor:{c:'badge-blue',l:'Editor'},viewer:{c:'badge-gray',l:'Visor'},
  };
  const {c,l}=map[status]||{c:'badge-gray',l:status};
  return <span className={`badge ${c}`}>{l}</span>;
}

/* ── MODAL ───────────────────────────────────────────── */
function Modal({title,onClose,children,maxWidth='640px'}){
  return <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
    <div className="modal" style={{maxWidth}}>
      <div className="flex items-center gap-3 mb-4">
        <h2 className="modal-title" style={{margin:0}}>{title}</h2>
        <button className="btn btn-secondary btn-sm btn-icon ml-auto" onClick={onClose}>✕</button>
      </div>
      {children}
    </div>
  </div>;
}

/* ── CONFIRM MODAL ───────────────────────────────────── */
function Confirm({msg,onConfirm,onClose}){
  return <Modal title="Confirmar acción" onClose={onClose} maxWidth="400px">
    <p style={{color:'var(--text2)',lineHeight:1.6}}>{msg}</p>
    <div className="modal-actions">
      <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
      <button className="btn btn-danger" onClick={()=>{onConfirm();onClose();}}>Confirmar</button>
    </div>
  </Modal>;
}

/* ── SEARCH BAR ──────────────────────────────────────── */
function SearchBar({value,onChange,placeholder='Buscar...'}){
  return <div className="search-bar">
    <span>🔍</span>
    <input value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}/>
    {value&&<button style={{background:'none',border:'none',color:'var(--text2)',cursor:'pointer'}} onClick={()=>onChange('')}>✕</button>}
  </div>;
}

/* ── CHART WRAPPER ───────────────────────────────────── */
function ChartWrap({type,data,options,height=220}){
  const ref=useRef();const chart=useRef();
  useEffect(()=>{
    if(chart.current) chart.current.destroy();
    if(!ref.current) return;
    chart.current=new Chart(ref.current,{type,data,options:{
      responsive:true,maintainAspectRatio:false,
      plugins:{legend:{labels:{color:'#9aa0bc',font:{family:'DM Sans'}}}},
      scales:type!=='pie'&&type!=='doughnut'?{
        x:{ticks:{color:'#5a607a'},grid:{color:'rgba(255,255,255,.04)'}},
        y:{ticks:{color:'#5a607a'},grid:{color:'rgba(255,255,255,.06)'}},
      }:{},
      ...options
    }});
    return()=>chart.current?.destroy();
  },[data]);
  return <div style={{height}}><canvas ref={ref}/></div>;
}

/* ═══════════════════════════════════════════════════════
   MODULES
═══════════════════════════════════════════════════════ */

/* ── DASHBOARD BI ────────────────────────────────────── */
function Dashboard(){
  const [bi,setBi]=useState(null);
  const {toast}=useApp();
  useEffect(()=>{
    api.get('/api/bi/summary').then(setBi).catch(e=>toast(e.message,'error'));
  },[]);
  if(!bi) return <div style={{textAlign:'center',padding:60}}><div className="spin" style={{fontSize:32}}>⚙️</div></div>;
  const {inventory:inv,finance:fin,payroll:pay,production:prod,accounting:acc}=bi;

  const trendData={
    labels:fin.trend.map(t=>t.month),
    datasets:[
      {label:'Ingresos',data:fin.trend.map(t=>t.income),borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.08)',tension:.4,fill:true},
      {label:'Egresos',data:fin.trend.map(t=>t.expenses),borderColor:'#ef4444',backgroundColor:'rgba(239,68,68,.08)',tension:.4,fill:true},
    ]
  };
  const catData={
    labels:inv.by_category.map(c=>c.category),
    datasets:[{data:inv.by_category.map(c=>c.value),backgroundColor:['#6c63ff','#22c55e','#f59e0b','#3b82f6','#f97316','#a855f7','#ef4444']}]
  };

  return <div>
    <div className="grid g4" style={{marginBottom:16}}>
      {[
        {icon:'📦',label:'Valor Inventario',val:fmt.cur(inv.total_value),sub:`${inv.total_items} ítems · ${inv.low_stock_count} bajo mín`,color:'#6c63ff'},
        {icon:'💰',label:'Ingresos del Mes',val:fmt.cur(fin.month_income),sub:`Utilidad: ${fmt.cur(fin.month_profit)}`,color:'#22c55e'},
        {icon:'👷',label:'Planilla del Mes',val:fmt.cur(pay.month_total),sub:`${pay.employee_count} empleados`,color:'#f59e0b'},
        {icon:'🏭',label:'Producción Activa',val:prod.in_progress,sub:`${prod.completed} completadas · ${prod.total_orders} total`,color:'#3b82f6'},
      ].map((s,i)=>(
        <div key={i} className="stat-card">
          <div className="stat-icon" style={{background:`${s.color}22`}}>{s.icon}</div>
          <div className="stat-value" style={{color:s.color}}>{s.val}</div>
          <div className="stat-label">{s.label}</div>
          <div className="stat-sub">{s.sub}</div>
        </div>
      ))}
    </div>
    <div className="grid g2" style={{marginBottom:16}}>
      <div className="card">
        <div className="card-head"><span className="card-title">📈 Tendencia Financiera</span></div>
        <ChartWrap type="line" data={trendData}/>
      </div>
      <div className="card">
        <div className="card-head"><span className="card-title">🗂 Inventario por Categoría</span></div>
        <ChartWrap type="doughnut" data={catData}/>
      </div>
    </div>
    <div className="grid g3">
      <div className="card">
        <div className="card-head"><span className="card-title">💳 Balance del Mes</span></div>
        <div style={{display:'flex',flexDirection:'column',gap:12}}>
          {[
            {l:'Ingresos',v:fin.month_income,c:'var(--green)'},
            {l:'Egresos',v:fin.month_expenses,c:'var(--red)'},
            {l:'Resultado',v:fin.month_profit,c:fin.month_profit>=0?'var(--green)':'var(--red)'},
          ].map((r,i)=>(
            <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid var(--border)'}}>
              <span style={{color:'var(--text2)',fontSize:13}}>{r.l}</span>
              <span style={{color:r.c,fontFamily:'var(--font-head)',fontWeight:700}}>{fmt.cur(r.v)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="card-head"><span className="card-title">📒 Contabilidad</span></div>
        {[
          {l:'Total Débitos',v:acc.total_debit,c:'var(--text)'},
          {l:'Total Créditos',v:acc.total_credit,c:'var(--text)'},
          {l:'Balance',v:acc.balance,c:acc.balance>=0?'var(--green)':'var(--red)'},
        ].map((r,i)=>(
          <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid var(--border)'}}>
            <span style={{color:'var(--text2)',fontSize:13}}>{r.l}</span>
            <span style={{color:r.c,fontFamily:'var(--font-head)',fontWeight:700}}>{fmt.cur(r.v)}</span>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-head"><span className="card-title">🏭 Estado Producción</span></div>
        {[
          {l:'En Curso',v:prod.in_progress,c:'var(--blue)'},
          {l:'Completadas',v:prod.completed,c:'var(--green)'},
          {l:'Total Órdenes',v:prod.total_orders,c:'var(--text)'},
        ].map((r,i)=>(
          <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid var(--border)'}}>
            <span style={{color:'var(--text2)',fontSize:13}}>{r.l}</span>
            <span style={{color:r.c,fontFamily:'var(--font-head)',fontWeight:700,fontSize:22}}>{r.v}</span>
          </div>
        ))}
      </div>
    </div>
  </div>;
}

/* ── INVENTORY MODULE ────────────────────────────────── */
function Inventory(){
  const [items,setItems]=useState([]);
  const [search,setSearch]=useState('');
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast,user}=useApp();
  const canEdit=user.role!=='viewer';

  const load=()=>api.get('/api/inventory').then(setItems).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const openNew=()=>{setForm({code:'',name:'',category:'',unit:'unidad',quantity:0,min_stock:0,cost_price:0,sale_price:0,supplier:'',location:''});setModal('form');};
  const openEdit=(i)=>{setForm({...i});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/inventory/${form.id}`,form);
      else await api.post('/api/inventory',form);
      toast(form.id?'Ítem actualizado':'Ítem creado','success');
      setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar este ítem del inventario?',fn:async()=>{
    await api.del(`/api/inventory/${id}`);toast('Eliminado','success');load();
  }});

  const filtered=items.filter(i=>i.name.toLowerCase().includes(search.toLowerCase())||i.code.toLowerCase().includes(search.toLowerCase()));

  return <div>
    <div className="flex items-center gap-3 mb-4">
      <SearchBar value={search} onChange={setSearch} placeholder="Buscar por nombre o código..."/>
      {canEdit&&<button className="btn btn-primary ml-auto" onClick={openNew}>+ Nuevo Ítem</button>}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Código</th><th>Nombre</th><th>Categoría</th><th>Cantidad</th>
            <th>Precio Costo</th><th>Precio Venta</th><th>Proveedor</th><th>Estado</th>
            {canEdit&&<th>Acciones</th>}
          </tr></thead>
          <tbody>{filtered.length===0?<tr><td colSpan={9}><div className="empty-state"><h3>Sin resultados</h3></div></td></tr>:
            filtered.map(i=>(
              <tr key={i.id}>
                <td className="td-mono">{i.code}</td>
                <td><strong>{i.name}</strong></td>
                <td><span className="chip">{i.category||'—'}</span></td>
                <td>
                  <div>{fmt.num(i.quantity)} {i.unit}</div>
                  {i.quantity<=i.min_stock&&<div style={{fontSize:11,color:'var(--yellow)'}}>⚠ Mín: {i.min_stock}</div>}
                </td>
                <td className="td-mono">{fmt.cur(i.cost_price)}</td>
                <td className="td-mono">{fmt.cur(i.sale_price)}</td>
                <td>{i.supplier||'—'}</td>
                <td><StatusBadge status={i.status}/></td>
                {canEdit&&<td>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(i)}>✏</button>
                    <button className="btn btn-danger btn-sm" onClick={()=>del(i.id)}>🗑</button>
                  </div>
                </td>}
              </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Ítem':'Nuevo Ítem de Inventario'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group"><label>Código</label><input value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/></div>
        <div className="form-group"><label>Nombre</label><input value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></div>
        <div className="form-group"><label>Categoría</label><input value={form.category} onChange={e=>setForm({...form,category:e.target.value})}/></div>
        <div className="form-group"><label>Unidad</label><input value={form.unit} onChange={e=>setForm({...form,unit:e.target.value})}/></div>
        <div className="form-group"><label>Cantidad</label><input type="number" value={form.quantity} onChange={e=>setForm({...form,quantity:+e.target.value})}/></div>
        <div className="form-group"><label>Stock Mínimo</label><input type="number" value={form.min_stock} onChange={e=>setForm({...form,min_stock:+e.target.value})}/></div>
        <div className="form-group"><label>Precio Costo (₲)</label><input type="number" value={form.cost_price} onChange={e=>setForm({...form,cost_price:+e.target.value})}/></div>
        <div className="form-group"><label>Precio Venta (₲)</label><input type="number" value={form.sale_price} onChange={e=>setForm({...form,sale_price:+e.target.value})}/></div>
        <div className="form-group"><label>Proveedor</label><input value={form.supplier} onChange={e=>setForm({...form,supplier:e.target.value})}/></div>
        <div className="form-group"><label>Ubicación</label><input value={form.location} onChange={e=>setForm({...form,location:e.target.value})}/></div>
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── PAYROLL MODULE ──────────────────────────────────── */
function Payroll(){
  const [records,setRecords]=useState([]);
  const [search,setSearch]=useState('');
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast,user}=useApp();
  const canEdit=user.role!=='viewer';
  const now=new Date();

  const load=()=>api.get('/api/payroll').then(setRecords).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const openNew=()=>{setForm({employee_name:'',employee_id_num:'',department:'',position:'',base_salary:0,bonus:0,overtime:0,deductions:0,ips:0,period_month:now.getMonth()+1,period_year:now.getFullYear(),status:'pending'});setModal('form');};
  const openEdit=(r)=>{setForm({...r});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/payroll/${form.id}`,form);
      else await api.post('/api/payroll',form);
      toast('Guardado correctamente','success');setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar este registro de planilla?',fn:async()=>{await api.del(`/api/payroll/${id}`);toast('Eliminado','success');load();}});
  const net=(f)=>((f.base_salary||0)+(f.bonus||0)+(f.overtime||0)-(f.deductions||0)-(f.ips||0));

  const filtered=records.filter(r=>r.employee_name.toLowerCase().includes(search.toLowerCase()));
  const totals={total:filtered.reduce((s,r)=>s+r.net_salary,0)};

  return <div>
    <div className="flex items-center gap-3 mb-4">
      <SearchBar value={search} onChange={setSearch} placeholder="Buscar empleado..."/>
      {canEdit&&<button className="btn btn-primary ml-auto" onClick={openNew}>+ Nuevo Registro</button>}
    </div>
    <div className="grid g3 mb-4">
      {[
        {l:'Total Neto del Filtro',v:fmt.cur(totals.total),i:'💵'},
        {l:'Registros',v:filtered.length,i:'📋'},
        {l:'Pagados',v:filtered.filter(r=>r.status==='paid').length,i:'✅'},
      ].map((s,i)=>(
        <div key={i} className="stat-card" style={{flexDirection:'row',alignItems:'center',gap:14}}>
          <div style={{fontSize:26}}>{s.i}</div>
          <div><div style={{fontFamily:'var(--font-head)',fontWeight:700,fontSize:20}}>{s.v}</div>
          <div style={{fontSize:12,color:'var(--text2)'}}>{s.l}</div></div>
        </div>
      ))}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Empleado</th><th>Dep./Cargo</th><th>Salario Base</th>
            <th>Bonos/Extras</th><th>Descuentos</th><th>IPS</th><th>Neto</th>
            <th>Período</th><th>Estado</th>
            {canEdit&&<th>Acciones</th>}
          </tr></thead>
          <tbody>{filtered.length===0?<tr><td colSpan={10}><div className="empty-state"><h3>Sin registros</h3></div></td></tr>:
            filtered.map(r=>(
              <tr key={r.id}>
                <td><strong>{r.employee_name}</strong><br/><span style={{fontSize:11,color:'var(--text3)'}}>{r.employee_id_num}</span></td>
                <td><div style={{fontSize:12}}>{r.department}</div><div style={{fontSize:11,color:'var(--text3)'}}>{r.position}</div></td>
                <td className="td-mono">{fmt.cur(r.base_salary)}</td>
                <td className="td-mono text-green">+{fmt.cur(r.bonus+r.overtime)}</td>
                <td className="td-mono text-red">-{fmt.cur(r.deductions)}</td>
                <td className="td-mono text-red">-{fmt.cur(r.ips)}</td>
                <td className="td-mono" style={{fontWeight:700,color:'var(--green)'}}>{fmt.cur(r.net_salary)}</td>
                <td>{String(r.period_month).padStart(2,'0')}/{r.period_year}</td>
                <td><StatusBadge status={r.status}/></td>
                {canEdit&&<td>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(r)}>✏</button>
                    <button className="btn btn-danger btn-sm" onClick={()=>del(r.id)}>🗑</button>
                  </div>
                </td>}
              </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Registro':'Nuevo Registro de Planilla'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group"><label>Nombre Empleado</label><input value={form.employee_name} onChange={e=>setForm({...form,employee_name:e.target.value})}/></div>
        <div className="form-group"><label>CI / ID</label><input value={form.employee_id_num} onChange={e=>setForm({...form,employee_id_num:e.target.value})}/></div>
        <div className="form-group"><label>Departamento</label><input value={form.department} onChange={e=>setForm({...form,department:e.target.value})}/></div>
        <div className="form-group"><label>Cargo</label><input value={form.position} onChange={e=>setForm({...form,position:e.target.value})}/></div>
        <div className="form-group"><label>Salario Base (₲)</label><input type="number" value={form.base_salary} onChange={e=>setForm({...form,base_salary:+e.target.value})}/></div>
        <div className="form-group"><label>Bonos (₲)</label><input type="number" value={form.bonus} onChange={e=>setForm({...form,bonus:+e.target.value})}/></div>
        <div className="form-group"><label>Horas Extra (₲)</label><input type="number" value={form.overtime} onChange={e=>setForm({...form,overtime:+e.target.value})}/></div>
        <div className="form-group"><label>Descuentos (₲)</label><input type="number" value={form.deductions} onChange={e=>setForm({...form,deductions:+e.target.value})}/></div>
        <div className="form-group"><label>IPS (₲)</label><input type="number" value={form.ips} onChange={e=>setForm({...form,ips:+e.target.value})}/></div>
        <div className="form-group"><label>Estado</label>
          <select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>
            <option value="pending">Pendiente</option>
            <option value="paid">Pagado</option>
            <option value="cancelled">Cancelado</option>
          </select>
        </div>
        <div className="form-group"><label>Mes</label><input type="number" min="1" max="12" value={form.period_month} onChange={e=>setForm({...form,period_month:+e.target.value})}/></div>
        <div className="form-group"><label>Año</label><input type="number" value={form.period_year} onChange={e=>setForm({...form,period_year:+e.target.value})}/></div>
      </div>
      <div className="card" style={{background:'var(--surface2)',marginTop:8}}>
        <strong>Salario Neto estimado: <span style={{color:'var(--green)',fontFamily:'var(--font-head)'}}>{fmt.cur(net(form))}</span></strong>
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── PRODUCTION MODULE ───────────────────────────────── */
function Production(){
  const [orders,setOrders]=useState([]);
  const [search,setSearch]=useState('');
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast,user}=useApp();
  const canEdit=user.role!=='viewer';

  const load=()=>api.get('/api/production').then(setOrders).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const toDateInput=(s)=>s?new Date(s).toISOString().slice(0,10):'';
  const openNew=()=>{setForm({product_name:'',quantity_planned:0,quantity_done:0,unit:'unidad',start_date:'',end_date:'',status:'draft',responsible:'',notes:'',cost_materials:0,cost_labor:0,cost_overhead:0});setModal('form');};
  const openEdit=(o)=>{setForm({...o,start_date:toDateInput(o.start_date),end_date:toDateInput(o.end_date)});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/production/${form.id}`,form);
      else await api.post('/api/production',form);
      toast('Guardado','success');setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar esta orden?',fn:async()=>{await api.del(`/api/production/${id}`);toast('Eliminado','success');load();}});

  const filtered=orders.filter(o=>o.product_name.toLowerCase().includes(search.toLowerCase())||o.order_number?.includes(search));
  const statusColors={draft:'var(--text3)',in_progress:'var(--blue)',done:'var(--green)',cancelled:'var(--red)'};

  return <div>
    <div className="flex items-center gap-3 mb-4">
      <SearchBar value={search} onChange={setSearch} placeholder="Buscar producto u orden..."/>
      {canEdit&&<button className="btn btn-primary ml-auto" onClick={openNew}>+ Nueva Orden</button>}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Orden</th><th>Producto</th><th>Progreso</th>
            <th>Fechas</th><th>Responsable</th>
            <th>Costo Total</th><th>Estado</th>
            {canEdit&&<th>Acciones</th>}
          </tr></thead>
          <tbody>{filtered.length===0?<tr><td colSpan={8}><div className="empty-state"><h3>Sin órdenes</h3></div></td></tr>:
            filtered.map(o=>(
              <tr key={o.id}>
                <td className="td-mono" style={{color:'var(--accent2)'}}>{o.order_number}</td>
                <td><strong>{o.product_name}</strong></td>
                <td>
                  <div style={{minWidth:100}}>
                    <div style={{fontSize:12,marginBottom:4}}>{fmt.num(o.quantity_done)}/{fmt.num(o.quantity_planned)} {o.unit} · <strong>{o.progress}%</strong></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{width:`${o.progress}%`,background:statusColors[o.status]||'var(--accent)'}}/>
                    </div>
                  </div>
                </td>
                <td style={{fontSize:12}}>
                  <div>Inicio: {fmt.date(o.start_date)}</div>
                  <div>Fin: {fmt.date(o.end_date)}</div>
                </td>
                <td>{o.responsible||'—'}</td>
                <td className="td-mono">{fmt.cur(o.total_cost)}</td>
                <td><StatusBadge status={o.status}/></td>
                {canEdit&&<td>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(o)}>✏</button>
                    <button className="btn btn-danger btn-sm" onClick={()=>del(o.id)}>🗑</button>
                  </div>
                </td>}
              </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Orden':'Nueva Orden de Producción'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group" style={{gridColumn:'span 2'}}><label>Producto</label><input value={form.product_name} onChange={e=>setForm({...form,product_name:e.target.value})}/></div>
        <div className="form-group"><label>Cantidad Planificada</label><input type="number" value={form.quantity_planned} onChange={e=>setForm({...form,quantity_planned:+e.target.value})}/></div>
        <div className="form-group"><label>Cantidad Producida</label><input type="number" value={form.quantity_done} onChange={e=>setForm({...form,quantity_done:+e.target.value})}/></div>
        <div className="form-group"><label>Unidad</label><input value={form.unit} onChange={e=>setForm({...form,unit:e.target.value})}/></div>
        <div className="form-group"><label>Estado</label>
          <select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>
            <option value="draft">Borrador</option><option value="in_progress">En Curso</option>
            <option value="done">Completado</option><option value="cancelled">Cancelado</option>
          </select>
        </div>
        <div className="form-group"><label>Fecha Inicio</label><input type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/></div>
        <div className="form-group"><label>Fecha Fin</label><input type="date" value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/></div>
        <div className="form-group"><label>Responsable</label><input value={form.responsible} onChange={e=>setForm({...form,responsible:e.target.value})}/></div>
        <div className="form-group"><label>Costo Mat. (₲)</label><input type="number" value={form.cost_materials} onChange={e=>setForm({...form,cost_materials:+e.target.value})}/></div>
        <div className="form-group"><label>Costo M.O. (₲)</label><input type="number" value={form.cost_labor} onChange={e=>setForm({...form,cost_labor:+e.target.value})}/></div>
        <div className="form-group"><label>Gastos Ind. (₲)</label><input type="number" value={form.cost_overhead} onChange={e=>setForm({...form,cost_overhead:+e.target.value})}/></div>
      </div>
      <div className="form-group"><label>Notas</label><textarea value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── FINANCE MODULE ──────────────────────────────────── */
function Finance(){
  const [txs,setTxs]=useState([]);
  const [search,setSearch]=useState('');
  const [typeFilter,setTypeFilter]=useState('all');
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast,user}=useApp();
  const canEdit=user.role!=='viewer';
  const now=new Date();

  const load=()=>api.get('/api/finance').then(setTxs).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const openNew=()=>{setForm({type:'income',category:'',description:'',amount:0,currency:'PYG',account:'',reference:'',date:now.toISOString().slice(0,10)});setModal('form');};
  const openEdit=(t)=>{setForm({...t,date:t.date?new Date(t.date).toISOString().slice(0,10):''});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/finance/${form.id}`,form);
      else await api.post('/api/finance',form);
      toast('Transacción guardada','success');setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar esta transacción?',fn:async()=>{await api.del(`/api/finance/${id}`);toast('Eliminado','success');load();}});

  const filtered=txs.filter(t=>{
    const matchSearch=t.description.toLowerCase().includes(search.toLowerCase())||t.category?.toLowerCase().includes(search.toLowerCase());
    const matchType=typeFilter==='all'||t.type===typeFilter;
    return matchSearch&&matchType;
  });
  const income=filtered.filter(t=>t.type==='income').reduce((s,t)=>s+t.amount,0);
  const expense=filtered.filter(t=>t.type==='expense').reduce((s,t)=>s+t.amount,0);

  return <div>
    <div className="flex items-center gap-3 mb-4" style={{flexWrap:'wrap'}}>
      <SearchBar value={search} onChange={setSearch} placeholder="Buscar transacción..."/>
      <div className="tabs" style={{margin:0}}>
        {['all','income','expense','transfer'].map(t=>(
          <div key={t} className={`tab ${typeFilter===t?'active':''}`} onClick={()=>setTypeFilter(t)}>
            {t==='all'?'Todo':t==='income'?'Ingresos':t==='expense'?'Egresos':'Transf.'}
          </div>
        ))}
      </div>
      {canEdit&&<button className="btn btn-primary ml-auto" onClick={openNew}>+ Nueva Transacción</button>}
    </div>
    <div className="grid g3 mb-4">
      {[
        {l:'Ingresos (filtro)',v:fmt.cur(income),c:'var(--green)',i:'⬆'},
        {l:'Egresos (filtro)',v:fmt.cur(expense),c:'var(--red)',i:'⬇'},
        {l:'Balance (filtro)',v:fmt.cur(income-expense),c:income-expense>=0?'var(--green)':'var(--red)',i:'⚖'},
      ].map((s,i)=>(
        <div key={i} className="stat-card" style={{flexDirection:'row',gap:14}}>
          <div style={{fontSize:26}}>{s.i}</div>
          <div><div style={{fontFamily:'var(--font-head)',fontWeight:700,fontSize:20,color:s.c}}>{s.v}</div>
          <div style={{fontSize:12,color:'var(--text2)'}}>{s.l}</div></div>
        </div>
      ))}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Fecha</th><th>Tipo</th><th>Categoría</th><th>Descripción</th>
            <th>Monto</th><th>Cuenta</th><th>Ref.</th>
            {canEdit&&<th>Acciones</th>}
          </tr></thead>
          <tbody>{filtered.length===0?<tr><td colSpan={8}><div className="empty-state"><h3>Sin transacciones</h3></div></td></tr>:
            filtered.map(t=>(
              <tr key={t.id}>
                <td style={{fontSize:12}}>{fmt.date(t.date)}</td>
                <td><StatusBadge status={t.type}/></td>
                <td><span className="chip">{t.category||'—'}</span></td>
                <td>{t.description}</td>
                <td className="td-mono" style={{color:t.type==='income'?'var(--green)':t.type==='expense'?'var(--red)':'var(--text)'}}>
                  {t.type==='expense'?'-':''}{fmt.cur(t.amount,t.currency)}
                </td>
                <td style={{fontSize:12}}>{t.account||'—'}</td>
                <td className="td-mono" style={{fontSize:11}}>{t.reference||'—'}</td>
                {canEdit&&<td>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(t)}>✏</button>
                    <button className="btn btn-danger btn-sm" onClick={()=>del(t.id)}>🗑</button>
                  </div>
                </td>}
              </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Transacción':'Nueva Transacción'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group"><label>Tipo</label>
          <select value={form.type} onChange={e=>setForm({...form,type:e.target.value})}>
            <option value="income">Ingreso</option><option value="expense">Egreso</option><option value="transfer">Transferencia</option>
          </select>
        </div>
        <div className="form-group"><label>Categoría</label><input value={form.category} onChange={e=>setForm({...form,category:e.target.value})}/></div>
        <div className="form-group" style={{gridColumn:'span 2'}}><label>Descripción</label><input value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></div>
        <div className="form-group"><label>Monto</label><input type="number" value={form.amount} onChange={e=>setForm({...form,amount:+e.target.value})}/></div>
        <div className="form-group"><label>Moneda</label>
          <select value={form.currency} onChange={e=>setForm({...form,currency:e.target.value})}>
            <option value="PYG">PYG (₲)</option><option value="USD">USD ($)</option><option value="BRL">BRL (R$)</option><option value="ARS">ARS</option>
          </select>
        </div>
        <div className="form-group"><label>Cuenta</label><input value={form.account} onChange={e=>setForm({...form,account:e.target.value})}/></div>
        <div className="form-group"><label>Referencia</label><input value={form.reference} onChange={e=>setForm({...form,reference:e.target.value})}/></div>
        <div className="form-group"><label>Fecha</label><input type="date" value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></div>
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── ACCOUNTING MODULE ───────────────────────────────── */
function Accounting(){
  const [entries,setEntries]=useState([]);
  const [search,setSearch]=useState('');
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast,user}=useApp();
  const canEdit=user.role!=='viewer';
  const now=new Date();

  const load=()=>api.get('/api/accounting').then(setEntries).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const openNew=()=>{setForm({date:now.toISOString().slice(0,10),description:'',account_code:'',account_name:'',debit:0,credit:0,reference:'',period:now.toISOString().slice(0,7)});setModal('form');};
  const openEdit=(e)=>{setForm({...e,date:e.date?new Date(e.date).toISOString().slice(0,10):''});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/accounting/${form.id}`,form);
      else await api.post('/api/accounting',form);
      toast('Asiento guardado','success');setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar este asiento contable?',fn:async()=>{await api.del(`/api/accounting/${id}`);toast('Eliminado','success');load();}});

  const filtered=entries.filter(e=>e.description?.toLowerCase().includes(search.toLowerCase())||e.account_code?.includes(search)||e.account_name?.toLowerCase().includes(search.toLowerCase()));
  const totalDebit=filtered.reduce((s,e)=>s+e.debit,0);
  const totalCredit=filtered.reduce((s,e)=>s+e.credit,0);

  return <div>
    <div className="flex items-center gap-3 mb-4">
      <SearchBar value={search} onChange={setSearch} placeholder="Buscar cuenta o descripción..."/>
      {canEdit&&<button className="btn btn-primary ml-auto" onClick={openNew}>+ Nuevo Asiento</button>}
    </div>
    <div className="grid g3 mb-4">
      {[
        {l:'Total Débitos',v:fmt.cur(totalDebit),c:'var(--blue)'},
        {l:'Total Créditos',v:fmt.cur(totalCredit),c:'var(--orange)'},
        {l:'Balance',v:fmt.cur(totalDebit-totalCredit),c:totalDebit-totalCredit>=0?'var(--green)':'var(--red)'},
      ].map((s,i)=>(
        <div key={i} className="card" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <span style={{color:'var(--text2)',fontSize:13}}>{s.l}</span>
          <span style={{fontFamily:'var(--font-head)',fontWeight:700,fontSize:18,color:s.c}}>{s.v}</span>
        </div>
      ))}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Asiento</th><th>Fecha</th><th>Cuenta</th><th>Descripción</th>
            <th>Débito</th><th>Crédito</th><th>Período</th><th>Registrado por</th>
            {canEdit&&<th>Acciones</th>}
          </tr></thead>
          <tbody>
            {filtered.length===0?<tr><td colSpan={9}><div className="empty-state"><h3>Sin asientos</h3></div></td></tr>:
            filtered.map(e=>(
              <tr key={e.id}>
                <td className="td-mono" style={{color:'var(--accent2)',fontSize:11}}>{e.entry_number}</td>
                <td style={{fontSize:12}}>{fmt.date(e.date)}</td>
                <td><div className="td-mono" style={{fontSize:11}}>{e.account_code}</div><div style={{fontSize:12}}>{e.account_name}</div></td>
                <td>{e.description}</td>
                <td className="td-mono" style={{color:'var(--blue)'}}>{e.debit>0?fmt.cur(e.debit):'—'}</td>
                <td className="td-mono" style={{color:'var(--orange)'}}>{e.credit>0?fmt.cur(e.credit):'—'}</td>
                <td className="td-mono" style={{fontSize:11}}>{e.period}</td>
                <td style={{fontSize:12}}>{e.created_by}</td>
                {canEdit&&<td>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(e)}>✏</button>
                    {!e.is_closed&&<button className="btn btn-danger btn-sm" onClick={()=>del(e.id)}>🗑</button>}
                  </div>
                </td>}
              </tr>
            ))}
            {filtered.length>0&&<tr style={{background:'var(--surface2)',fontWeight:700}}>
              <td colSpan={4} style={{fontFamily:'var(--font-head)',fontSize:13}}>TOTALES</td>
              <td className="td-mono" style={{color:'var(--blue)'}}>{fmt.cur(totalDebit)}</td>
              <td className="td-mono" style={{color:'var(--orange)'}}>{fmt.cur(totalCredit)}</td>
              <td colSpan={3}/>
            </tr>}
          </tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Asiento':'Nuevo Asiento Contable'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group"><label>Fecha</label><input type="date" value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></div>
        <div className="form-group"><label>Período</label><input type="month" value={form.period} onChange={e=>setForm({...form,period:e.target.value})}/></div>
        <div className="form-group"><label>Código de Cuenta</label><input value={form.account_code} onChange={e=>setForm({...form,account_code:e.target.value})} placeholder="Ej: 1.1.01"/></div>
        <div className="form-group"><label>Nombre de Cuenta</label><input value={form.account_name} onChange={e=>setForm({...form,account_name:e.target.value})}/></div>
        <div className="form-group" style={{gridColumn:'span 2'}}><label>Descripción</label><input value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></div>
        <div className="form-group"><label>Débito (₲)</label><input type="number" value={form.debit} onChange={e=>setForm({...form,debit:+e.target.value})}/></div>
        <div className="form-group"><label>Crédito (₲)</label><input type="number" value={form.credit} onChange={e=>setForm({...form,credit:+e.target.value})}/></div>
        <div className="form-group" style={{gridColumn:'span 2'}}><label>Referencia</label><input value={form.reference} onChange={e=>setForm({...form,reference:e.target.value})}/></div>
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── USERS MODULE (admin only) ───────────────────────── */
function Users(){
  const [users,setUsers]=useState([]);
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [confirm,setConfirm]=useState(null);
  const {toast}=useApp();

  const load=()=>api.get('/api/users').then(setUsers).catch(e=>toast(e.message,'error'));
  useEffect(()=>{load();},[]);

  const openNew=()=>{setForm({username:'',email:'',full_name:'',password:'',role:'viewer',department:'',is_active:true});setModal('form');};
  const openEdit=(u)=>{setForm({...u,password:''});setModal('form');};
  const save=async()=>{
    try{
      if(form.id) await api.put(`/api/users/${form.id}`,form);
      else await api.post('/api/users',form);
      toast(form.id?'Usuario actualizado':'Usuario creado','success');setModal(null);load();
    }catch(e){toast(e.message,'error');}
  };
  const del=(id)=>setConfirm({msg:'¿Eliminar este usuario permanentemente?',fn:async()=>{await api.del(`/api/users/${id}`);toast('Eliminado','success');load();}});

  return <div>
    <div className="flex items-center gap-3 mb-4">
      <h3 style={{fontFamily:'var(--font-head)'}}>Gestión de Usuarios</h3>
      <button className="btn btn-primary ml-auto" onClick={openNew}>+ Nuevo Usuario</button>
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Usuario</th><th>Nombre Completo</th><th>Email</th>
            <th>Rol</th><th>Departamento</th><th>Estado</th><th>Último Acceso</th><th>Acciones</th>
          </tr></thead>
          <tbody>{users.map(u=>(
            <tr key={u.id}>
              <td className="td-mono">{u.username}</td>
              <td><strong>{u.full_name}</strong></td>
              <td style={{fontSize:12}}>{u.email}</td>
              <td><StatusBadge status={u.role}/></td>
              <td>{u.department||'—'}</td>
              <td><StatusBadge status={u.is_active?'active':'inactive'}/></td>
              <td style={{fontSize:12}}>{fmt.date(u.last_login)}</td>
              <td>
                <div className="flex gap-2">
                  <button className="btn btn-secondary btn-sm" onClick={()=>openEdit(u)}>✏</button>
                  <button className="btn btn-danger btn-sm" onClick={()=>del(u.id)}>🗑</button>
                </div>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {modal==='form'&&<Modal title={form.id?'Editar Usuario':'Nuevo Usuario'} onClose={()=>setModal(null)}>
      <div className="form-grid">
        <div className="form-group"><label>Nombre de usuario</label><input value={form.username} onChange={e=>setForm({...form,username:e.target.value})} disabled={!!form.id}/></div>
        <div className="form-group"><label>Email</label><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></div>
        <div className="form-group" style={{gridColumn:'span 2'}}><label>Nombre Completo</label><input value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></div>
        <div className="form-group"><label>{form.id?'Nueva Contraseña (dejar vacío para no cambiar)':'Contraseña'}</label><input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></div>
        <div className="form-group"><label>Rol</label>
          <select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
            <option value="viewer">Visor (solo lectura)</option>
            <option value="editor">Editor</option>
            <option value="admin">Administrador</option>
          </select>
        </div>
        <div className="form-group"><label>Departamento</label><input value={form.department} onChange={e=>setForm({...form,department:e.target.value})}/></div>
        <div className="form-group" style={{justifyContent:'flex-end',flexDirection:'row',alignItems:'center',gap:10}}>
          <label style={{marginBottom:0}}>Activo</label>
          <input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})} style={{width:'auto'}}/>
        </div>
      </div>
      <div style={{background:'var(--surface2)',borderRadius:'var(--radius-sm)',padding:12,fontSize:12,color:'var(--text2)',marginTop:8}}>
        <strong>Roles:</strong> Visor = solo lectura · Editor = crear/editar · Admin = acceso total + usuarios + historial
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setModal(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={save}>Guardar</button>
      </div>
    </Modal>}
    {confirm&&<Confirm msg={confirm.msg} onConfirm={confirm.fn} onClose={()=>setConfirm(null)}/>}
  </div>;
}

/* ── AUDIT LOG (admin only) ──────────────────────────── */
function AuditLog(){
  const [logs,setLogs]=useState([]);
  const [module,setModule]=useState('all');
  const [detail,setDetail]=useState(null);
  const {toast}=useApp();

  const modules=['all','auth','users','inventory','payroll','production','finance','accounting'];
  useEffect(()=>{
    const url='/api/audit'+(module!=='all'?`?module=${module}`:'');
    api.get(url).then(setLogs).catch(e=>toast(e.message,'error'));
  },[module]);

  const actionColor={CREATE:'var(--green)',UPDATE:'var(--yellow)',DELETE:'var(--red)',LOGIN:'var(--blue)',CHANGE_PASSWORD:'var(--orange)'};

  return <div>
    <div className="flex items-center gap-3 mb-4" style={{flexWrap:'wrap'}}>
      <h3 style={{fontFamily:'var(--font-head)'}}>📋 Historial de Cambios</h3>
      <div style={{fontSize:12,color:'var(--text3)'}}>Solo visible para administradores</div>
    </div>
    <div className="tabs">
      {modules.map(m=>(
        <div key={m} className={`tab ${module===m?'active':''}`} onClick={()=>setModule(m)}>
          {m==='all'?'Todos':m.charAt(0).toUpperCase()+m.slice(1)}
        </div>
      ))}
    </div>
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Fecha/Hora</th><th>Usuario</th><th>Acción</th>
            <th>Módulo</th><th>Registro</th><th>IP</th><th>Detalle</th>
          </tr></thead>
          <tbody>{logs.length===0?<tr><td colSpan={7}><div className="empty-state"><h3>Sin registros</h3></div></td></tr>:
            logs.map(l=>(
              <tr key={l.id}>
                <td className="td-mono" style={{fontSize:11}}>{new Date(l.created_at).toLocaleString('es-PY')}</td>
                <td><strong>{l.username}</strong></td>
                <td><span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:700,color:actionColor[l.action]||'var(--text)'}}>{l.action}</span></td>
                <td><span className="chip">{l.module}</span></td>
                <td className="td-mono" style={{fontSize:11}}>{l.record_id||'—'}</td>
                <td className="td-mono" style={{fontSize:11}}>{l.ip_address||'—'}</td>
                <td>
                  {(l.old_values||l.new_values)&&
                    <button className="btn btn-secondary btn-sm" onClick={()=>setDetail(l)}>Ver</button>}
                </td>
              </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
    {detail&&<Modal title="Detalle del Cambio" onClose={()=>setDetail(null)} maxWidth="700px">
      <div className="grid g2">
        {detail.old_values&&<div>
          <div style={{fontSize:11,fontWeight:700,color:'var(--red)',marginBottom:8,textTransform:'uppercase'}}>Antes</div>
          <pre style={{background:'var(--surface2)',padding:12,borderRadius:'var(--radius-sm)',fontSize:11,color:'var(--text2)',overflow:'auto',maxHeight:300,fontFamily:'var(--font-mono)'}}>{JSON.stringify(detail.old_values,null,2)}</pre>
        </div>}
        {detail.new_values&&<div>
          <div style={{fontSize:11,fontWeight:700,color:'var(--green)',marginBottom:8,textTransform:'uppercase'}}>Después</div>
          <pre style={{background:'var(--surface2)',padding:12,borderRadius:'var(--radius-sm)',fontSize:11,color:'var(--text2)',overflow:'auto',maxHeight:300,fontFamily:'var(--font-mono)'}}>{JSON.stringify(detail.new_values,null,2)}</pre>
        </div>}
      </div>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={()=>setDetail(null)}>Cerrar</button>
      </div>
    </Modal>}
  </div>;
}

/* ── PROFILE / CHANGE PASSWORD ───────────────────────── */
function Profile(){
  const {user,toast}=useApp();
  const [form,setForm]=useState({current_password:'',new_password:'',confirm:''});

  const save=async()=>{
    if(form.new_password!==form.confirm){toast('Las contraseñas no coinciden','error');return;}
    try{
      await api.post('/api/auth/change-password',{current_password:form.current_password,new_password:form.new_password});
      toast('Contraseña actualizada','success');
      setForm({current_password:'',new_password:'',confirm:''});
    }catch(e){toast(e.message,'error');}
  };

  return <div style={{maxWidth:520}}>
    <div className="card mb-4">
      <div className="card-head"><span className="card-title">Mi Perfil</span></div>
      {[['Usuario',user.username],['Email',user.email],['Nombre',user.full_name],['Rol',user.role],['Departamento',user.department||'—']].map(([l,v])=>(
        <div key={l} style={{display:'flex',justifyContent:'space-between',padding:'9px 0',borderBottom:'1px solid var(--border)',fontSize:14}}>
          <span style={{color:'var(--text2)'}}>{l}</span>
          <span style={{fontWeight:600}}>{v}</span>
        </div>
      ))}
    </div>
    <div className="card">
      <div className="card-head"><span className="card-title">Cambiar Contraseña</span></div>
      <div className="form-group"><label>Contraseña Actual</label><input type="password" value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})}/></div>
      <div className="form-group"><label>Nueva Contraseña</label><input type="password" value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})}/></div>
      <div className="form-group"><label>Confirmar Nueva Contraseña</label><input type="password" value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})}/></div>
      <button className="btn btn-primary" onClick={save}>Actualizar Contraseña</button>
    </div>
  </div>;
}

/* ── LOGIN PAGE ──────────────────────────────────────── */
function LoginPage({onLogin}){
  const [form,setForm]=useState({username:'',password:''});
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');

  const submit=async()=>{
    setLoading(true);setError('');
    try{
      const res=await api.post('/api/auth/login',form);
      localStorage.setItem('erp_token',res.token);
      onLogin(res.user);
    }catch(e){setError(e.message);}
    setLoading(false);
  };

  return <div className="login-page">
    <div className="login-card">
      <div className="login-logo">
        <div className="logo-mark">S</div>
        <h1>Senda<span>ERP</span></h1>
        <p>Sistema de Gestión Empresarial</p>
      </div>
      {error&&<div style={{background:'rgba(239,68,68,.12)',border:'1px solid rgba(239,68,68,.3)',borderRadius:'var(--radius-sm)',padding:'10px 14px',marginBottom:16,fontSize:13,color:'var(--red)'}}>⚠ {error}</div>}
      <div className="form-group"><label>Usuario</label>
        <input value={form.username} onChange={e=>setForm({...form,username:e.target.value})}
          onKeyDown={e=>e.key==='Enter'&&submit()} placeholder="admin"/>
      </div>
      <div className="form-group"><label>Contraseña</label>
        <input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}
          onKeyDown={e=>e.key==='Enter'&&submit()} placeholder="••••••••"/>
      </div>
      <button className="btn btn-primary w-full" style={{marginTop:8,padding:'11px'}} onClick={submit} disabled={loading}>
        {loading?'Ingresando...':'Ingresar al Sistema'}
      </button>
      <div style={{textAlign:'center',marginTop:20,fontSize:12,color:'var(--text3)'}}>
        Credenciales por defecto: <strong style={{color:'var(--text2)'}}>admin / admin123</strong>
      </div>
    </div>
  </div>;
}

/* ═══════════════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════════════ */
const NAV=[
  {id:'dashboard',icon:'📊',label:'Dashboard BI',section:'Principal'},
  {id:'inventory',icon:'📦',label:'Inventario',section:'Módulos'},
  {id:'payroll',icon:'💵',label:'Planilla de Pagos',section:'Módulos'},
  {id:'production',icon:'🏭',label:'Producción',section:'Módulos'},
  {id:'finance',icon:'💰',label:'Finanzas',section:'Módulos'},
  {id:'accounting',icon:'📒',label:'Contabilidad',section:'Módulos'},
  {id:'users',icon:'👥',label:'Usuarios',section:'Admin',adminOnly:true},
  {id:'audit',icon:'🔍',label:'Historial',section:'Admin',adminOnly:true},
  {id:'profile',icon:'👤',label:'Mi Perfil',section:'Cuenta'},
];

const TITLES={dashboard:'Dashboard BI',inventory:'Inventario',payroll:'Planilla de Pagos',production:'Producción',finance:'Finanzas',accounting:'Contabilidad',users:'Gestión de Usuarios',audit:'Historial de Cambios',profile:'Mi Perfil'};

function App(){
  const [user,setUser]=useState(null);
  const [page,setPage]=useState('dashboard');
  const [toasts,setToasts]=useState([]);
  const [collapsed,setCollapsed]=useState(false);
  const [mobileOpen,setMobileOpen]=useState(false);

  const toast=(msg,type='info')=>{
    const id=Date.now();
    setToasts(p=>[...p,{id,msg,type}]);
    setTimeout(()=>setToasts(p=>p.filter(t=>t.id!==id)),3500);
  };

  useEffect(()=>{
    const token=localStorage.getItem('erp_token');
    if(token) api.get('/api/auth/me').then(setUser).catch(()=>localStorage.removeItem('erp_token'));
  },[]);

  const logout=()=>{localStorage.removeItem('erp_token');setUser(null);};

  if(!user) return <AppCtx.Provider value={{toast,user:null}}>
    <LoginPage onLogin={u=>{setUser(u);}}/>
    <ToastContainer toasts={toasts}/>
  </AppCtx.Provider>;

  const nav=NAV.filter(n=>!n.adminOnly||user.role==='admin');
  const sections=[...new Set(nav.map(n=>n.section))];

  const PAGES={dashboard:Dashboard,inventory:Inventory,payroll:Payroll,production:Production,finance:Finance,accounting:Accounting,users:Users,audit:AuditLog,profile:Profile};
  const PageComp=PAGES[page]||Dashboard;

  return <AppCtx.Provider value={{toast,user}}>
    <div className="app">
      {/* Overlay mobile */}
      {mobileOpen&&<div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.6)',zIndex:99}} onClick={()=>setMobileOpen(false)}/>}

      {/* SIDEBAR */}
      <aside className={`sidebar ${collapsed?'collapsed':''} ${mobileOpen?'mobile-open':''}`}>
        <div className="sidebar-logo">
          <div className="logo-mark">S</div>
          {!collapsed&&<div className="logo-text">Senda<span>ERP</span></div>}
          <button className="btn btn-secondary btn-sm btn-icon ml-auto" style={{flexShrink:0}}
            onClick={()=>setCollapsed(p=>!p)}>{collapsed?'→':'←'}</button>
        </div>
        <nav className="sidebar-nav">
          {sections.map(sec=>(
            <div key={sec}>
              {!collapsed&&<div className="nav-section">{sec}</div>}
              {nav.filter(n=>n.section===sec).map(n=>(
                <div key={n.id} className={`nav-item ${page===n.id?'active':''}`}
                  onClick={()=>{setPage(n.id);setMobileOpen(false);}}>
                  <span className="nav-icon">{n.icon}</span>
                  {!collapsed&&<span className="nav-label">{n.label}</span>}
                </div>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-card" onClick={()=>{setPage('profile');setMobileOpen(false);}}>
            <div className="avatar">{user.full_name.charAt(0)}</div>
            {!collapsed&&<div className="user-info">
              <div className="user-name">{user.full_name}</div>
              <div className="user-role">{user.role}</div>
            </div>}
          </div>
          {!collapsed&&<button className="btn btn-secondary w-full mt-2" style={{justifyContent:'center'}} onClick={logout}>
            Cerrar Sesión
          </button>}
        </div>
      </aside>

      {/* MAIN */}
      <main className="main">
        <div className="topbar">
          <button className="btn btn-secondary btn-sm btn-icon" style={{display:'none'}}
            id="mobile-menu-btn"
            onClick={()=>setMobileOpen(p=>!p)}>☰</button>
          <span className="topbar-title">{TITLES[page]}</span>
          <div className="topbar-actions">
            <span style={{fontSize:12,color:'var(--text3)'}}>
              {user.role==='admin'?'🔑 Admin':user.role==='editor'?'✏ Editor':'👁 Visor'}
            </span>
          </div>
        </div>
        <div className="content">
          <PageComp/>
        </div>
      </main>
    </div>
    <ToastContainer toasts={toasts}/>
    <style>{`@media(max-width:768px){#mobile-menu-btn{display:flex!important}}`}</style>
  </AppCtx.Provider>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/<path:path>')
def frontend(path=''):
    return HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ─────────────────────────────────────────────────────────────
# INIT DB + SEED
# ─────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        # Crear admin por defecto si no existe
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@sendaerp.com',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                full_name='Administrador del Sistema',
                role='admin',
                department='Administración'
            )
            db.session.add(admin)

            # Demo data — inventario
            for item in [
                InventoryItem(code='INV-001',name='Materia Prima A',category='Materiales',unit='kg',quantity=500,min_stock=100,cost_price=15000,sale_price=22000,supplier='Proveedor ABC',location='Bodega 1'),
                InventoryItem(code='INV-002',name='Producto Terminado X',category='Terminados',unit='unidad',quantity=80,min_stock=100,cost_price=250000,sale_price=380000,supplier='Producción Interna',location='Bodega 2'),
                InventoryItem(code='INV-003',name='Embalaje Caja Grande',category='Embalajes',unit='unidad',quantity=1200,min_stock=200,cost_price=3500,sale_price=5000,supplier='Papelería GS',location='Estante A'),
            ]:
                db.session.add(item)

            # Demo data — finanzas
            for tx in [
                FinanceTransaction(type='income',category='Ventas',description='Venta de productos terminados',amount=4500000,currency='PYG',account='Caja General',created_by='admin',date=datetime.utcnow()),
                FinanceTransaction(type='expense',category='Servicios',description='Pago de luz y agua',amount=850000,currency='PYG',account='Banco BNF',created_by='admin',date=datetime.utcnow()),
                FinanceTransaction(type='income',category='Servicios',description='Factura servicios consulting',amount=2000000,currency='PYG',account='Banco Itaú',created_by='admin',date=datetime.utcnow()),
            ]:
                db.session.add(tx)

            # Demo data — contabilidad
            for e in [
                AccountingEntry(entry_number='AST-2025-001',date=datetime.utcnow(),description='Ventas del mes',account_code='4.1.01',account_name='Ingresos por Ventas',credit=4500000,period='2025-06',created_by='admin'),
                AccountingEntry(entry_number='AST-2025-002',date=datetime.utcnow(),description='Costo de ventas',account_code='5.1.01',account_name='Costo de Ventas',debit=2200000,period='2025-06',created_by='admin'),
            ]:
                db.session.add(e)

            # Demo data — producción
            order = ProductionOrder(
                order_number='OP-20250601-A1B2',
                product_name='Producto Estrella 500ml',
                quantity_planned=1000,quantity_done=650,unit='unidad',
                start_date=datetime(2025,6,1),end_date=datetime(2025,6,30),
                status='in_progress',responsible='Juan Pérez',
                cost_materials=1200000,cost_labor=800000,cost_overhead=200000
            )
            db.session.add(order)

            # Demo data — planilla
            for r in [
                PayrollRecord(employee_name='María García',employee_id_num='1234567',department='Administración',position='Contadora',base_salary=3500000,bonus=200000,ips=315000,net_salary=3385000,period_month=6,period_year=2025,status='paid'),
                PayrollRecord(employee_name='Carlos López',employee_id_num='7654321',department='Producción',position='Operario',base_salary=2200000,overtime=300000,ips=198000,net_salary=2302000,period_month=6,period_year=2025,status='pending'),
            ]:
                db.session.add(r)

            db.session.commit()
            print("✅ Base de datos inicializada con datos de demostración")
            print("   Usuario admin creado: admin / admin123")


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("""
╔══════════════════════════════════════════════════════╗
║          SENDA ERP — Iniciando servidor              ║
║  URL:  http://localhost:5000                         ║
║  User: admin  |  Pass: admin123                      ║
╚══════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)