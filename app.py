import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Railway ma'lumotlar bazasi ulanishi
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///market_pro_final.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-123'

db = SQLAlchemy(app)

# Summa formatlash: 10.000
@app.template_filter('format_money')
def format_money(value):
    try:
        return "{:,.0f}".format(value).replace(',', '.')
    except:
        return value

# --- MODELLAR ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    buy_price = db.Column(db.Float, default=0)
    sell_price = db.Column(db.Float, default=0)
    stock = db.Column(db.Float, default=0)
    unit = db.Column(db.String(10), default='dona')

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

with app.app_context():
    db.create_all()

# --- YO'NALISHLAR ---
@app.route('/')
def index():
    search = request.args.get('search')
    query = Product.query
    if search:
        query = query.filter(Product.name.contains(search))
    products = query.all()
    return render_template('index.html', products=products)

@app.route('/ombor', methods=['GET', 'POST'])
def ombor():
    if request.method == 'POST':
        new_p = Product(
            name=request.form['name'],
            category=request.form['category'],
            buy_price=float(request.form.get('buy_price', 0)),
            sell_price=float(request.form.get('sell_price', 0)),
            stock=float(request.form.get('stock', 0)),
            unit=request.form.get('unit', 'dona')
        )
        db.session.add(new_p)
        db.session.commit()
        return redirect(url_for('ombor'))
    return render_template('ombor.html', products=Product.query.all())

@app.route('/sell/<int:id>', methods=['POST'])
def sell(id):
    p = Product.query.get_or_404(id)
    qty = float(request.form.get('qty', 0))
    paid = float(request.form.get('paid', 0))
    total = qty * p.sell_price
    
    sale = Sale(
        customer_name=request.form.get('customer_name', 'Mijoz'),
        product_name=p.name, quantity=qty, total_price=total,
        paid_amount=paid, debt_amount=max(0, total - paid),
        profit=(p.sell_price - p.buy_price) * qty
    )
    p.stock -= qty
    db.session.add(sale)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_product(id):
    p = Product.query.get_or_404(id)
    p.name = request.form['name']
    p.category = request.form['category']
    p.buy_price = float(request.form['buy_price'])
    p.sell_price = float(request.form['sell_price'])
    p.stock = float(request.form['stock'])
    p.unit = request.form['unit']
    db.session.commit()
    return redirect(url_for('ombor'))

@app.route('/qarzlar')
def qarzlar():
    debts = Sale.query.filter(Sale.debt_amount > 0).all()
    return render_template('qarzlar.html', debts=debts)

@app.route('/pay_debt/<int:id>', methods=['POST'])
def pay_debt(id):
    s = Sale.query.get_or_404(id)
    pay = float(request.form['pay_val'])
    s.debt_amount = max(0, s.debt_amount - pay)
    s.paid_amount += pay
    db.session.commit()
    return redirect(url_for('qarzlar'))

@app.route('/hisobot')
def hisobot():
    sales = Sale.query.all()
    return render_template('hisobot.html', 
        kassa=sum(s.paid_amount for s in sales),
        debt=sum(s.debt_amount for s in sales),
        prof=sum(s.profit for s in sales),
        sales=sales[::-1])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
