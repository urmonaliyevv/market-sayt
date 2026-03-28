import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pos-pro-secure-2026'

# Ma'lumotlar bazasi sozlamasi
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///market_v2.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MA'LUMOTLAR MODELI ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    buy_price = db.Column(db.Float, default=0)
    sell_price = db.Column(db.Float, default=0)
    stock = db.Column(db.Float, default=0)
    unit = db.Column(db.String(10), default='dona')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Egasi

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100))
    product_name = db.Column(db.String(100))
    quantity = db.Column(db.Float)
    total_price = db.Column(db.Float)
    paid_amount = db.Column(db.Float)
    debt_amount = db.Column(db.Float)
    profit = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Egasi

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Egasi

with app.app_context():
    db.create_all()

@app.template_filter('format_money')
def format_money(value):
    return "{:,.0f}".format(value or 0).replace(',', ' ')

# --- AVTORIZATSIYA ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user: return "Bu nom band!"
        new_user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password'])
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ASOSIY FUNKSIYALAR (FILTRLANGAN) ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    # FAQAT O'ZINING MAHSULOTLARI
    products = Product.query.filter_by(user_id=session['user_id']).all()
    return render_template('index.html', products=products)

@app.route('/bulk_sell', methods=['POST'])
def bulk_sell():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    items = data.get('items', [])
    paid = float(data.get('paid') or 0)
    customer = data.get('customer') or "Umumiy mijoz"
    
    total_sum = sum(i['price'] * i['qty'] for i in items)
    
    for i, item in enumerate(items):
        p = Product.query.filter_by(id=item['id'], user_id=session['user_id']).first()
        if p:
            qty = float(item['qty'])
            p.stock -= qty
            sale = Sale(
                customer_name=customer, product_name=p.name, quantity=qty,
                total_price=qty * p.sell_price, 
                paid_amount=paid if i == 0 else 0,
                debt_amount=max(0, total_sum - paid) if i == 0 else 0,
                profit=(p.sell_price - p.buy_price) * qty,
                user_id=session['user_id']
            )
            db.session.add(sale)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/ombor', methods=['GET', 'POST'])
def ombor():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        p = Product(
            name=request.form['name'], category=request.form['category'],
            buy_price=float(request.form['buy_price']), sell_price=float(request.form['sell_price']),
            stock=float(request.form['stock']), unit=request.form['unit'], 
            user_id=session['user_id']
        )
        db.session.add(p)
        db.session.commit()
        return redirect(url_for('ombor'))
    
    products = Product.query.filter_by(user_id=session['user_id']).all()
    return render_template('ombor.html', products=products)

@app.route('/edit/<int:id>', methods=['POST'])
def edit_product(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    p = Product.query.filter_by(id=id, user_id=session['user_id']).first_or_404()
    p.name = request.form['name']
    p.buy_price = float(request.form['buy_price'])
    p.sell_price = float(request.form['sell_price'])
    p.stock = float(request.form['stock'])
    db.session.commit()
    return redirect(url_for('ombor'))

@app.route('/hisobot')
def hisobot():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session['user_id']
    
    sales = Sale.query.filter_by(user_id=uid).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    products = Product.query.filter_by(user_id=uid).all()

    t_sales = sum(s.total_price for s in sales)
    t_exp = sum(e.amount for e in expenses)
    g_profit = sum(s.profit for s in sales)
    
    return render_template('hisobot.html', 
        sales=sales[::-1], expenses=expenses[::-1],
        total_sales=t_sales, net_profit=g_profit - t_exp, 
        total_expenses=t_exp, stock_value=sum(p.stock * p.buy_price for p in products))

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session: return redirect(url_for('login'))
    new_exp = Expense(
        description=request.form['desc'], 
        amount=float(request.form['amount']), 
        user_id=session['user_id']
    )
    db.session.add(new_exp)
    db.session.commit()
    return redirect(url_for('hisobot'))

@app.route('/qarzlar')
def qarzlar():
    if 'user_id' not in session: return redirect(url_for('login'))
    debts = Sale.query.filter(Sale.user_id == session['user_id'], Sale.debt_amount > 0).all()
    return render_template('qarzlar.html', debts=debts)

@app.route('/pay_debt/<int:id>', methods=['POST'])
def pay_debt(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    s = Sale.query.filter_by(id=id, user_id=session['user_id']).first_or_404()
    amt = float(request.form['pay_val'] or 0)
    s.debt_amount = max(0, s.debt_amount - amt)
    s.paid_amount += amt
    db.session.commit()
    return redirect(url_for('qarzlar'))

if __name__ == '__main__':
    app.run(debug=True)
