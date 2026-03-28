from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///market_pro.db'
app.config['SECRET_KEY'] = 'premium_secret_2026'
db = SQLAlchemy(app)

# Summani 18.000.000 ko'rinishida formatlash uchun filtr
@app.template_filter('format_money')
def format_money(value):
    try:
        return "{:,.0f}".format(value).replace(',', '.')
    except:
        return value

# --- MA'LUMOTLAR BAZASI MODELLARI ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    buy_price = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Float, default=0)
    unit = db.Column(db.String(10))

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

# --- YO'NALISHLAR (ROUTES) ---

@app.route('/')
def index():
    cat = request.args.get('category')
    search = request.args.get('search')
    query = Product.query
    if cat: query = query.filter_by(category=cat)
    if search: query = query.filter(Product.name.contains(search))
    products = query.all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('index.html', products=products, categories=categories)

@app.route('/ombor', methods=['GET', 'POST'])
def ombor():
    if request.method == 'POST':
        new_p = Product(
            name=request.form['name'],
            category=request.form['category'],
            buy_price=float(request.form['buy_price']),
            sell_price=float(request.form['sell_price']),
            stock=float(request.form['stock']),
            unit=request.form['unit']
        )
        db.session.add(new_p)
        db.session.commit()
        return redirect(url_for('ombor'))
    products = Product.query.all()
    return render_template('ombor.html', products=products)

@app.route('/edit_product/<int:id>', methods=['POST'])
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

@app.route('/sell/<int:id>', methods=['POST'])
def sell(id):
    p = Product.query.get_or_404(id)
    qty = float(request.form['qty'])
    paid = float(request.form['paid'])
    total = qty * p.sell_price
    profit = (p.sell_price - p.buy_price) * qty
    sale = Sale(
        customer_name=request.form.get('customer_name'),
        product_name=p.name, quantity=qty,
        total_price=total, paid_amount=paid,
        debt_amount=max(0, total - paid), profit=profit
    )
    p.stock -= qty
    db.session.add(sale)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/qarzlar')
def qarzlar():
    debts = Sale.query.filter(Sale.debt_amount > 0).all()
    return render_template('qarzlar.html', debts=debts)

@app.route('/pay_debt/<int:id>', methods=['POST'])
def pay_debt(id):
    sale = Sale.query.get_or_404(id)
    pay_val = float(request.form['pay_val'])
    sale.debt_amount = max(0, sale.debt_amount - pay_val)
    sale.paid_amount += pay_val
    db.session.commit()
    return redirect(url_for('qarzlar'))

@app.route('/hisobot')
def hisobot():
    sales = Sale.query.all()
    context = {
        'kassa': sum(s.paid_amount for s in sales),
        'debt': sum(s.debt_amount for s in sales),
        'prof': sum(s.profit for s in sales),
        'cost': sum((s.total_price - s.profit) for s in sales),
        'sales': sales[::-1]
    }
    return render_template('hisobot.html', **context)

if __name__ == '__main__':
    app.run(debug=True)