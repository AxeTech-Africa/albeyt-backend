from flask import Flask, request, render_template, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from flask_socketio import SocketIO, emit
import os
from flask_cors import CORS
from flask_migrate import Migrate

# Initialize Flask app
app = Flask(__name__)

# Flask configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # To suppress SQLAlchemy warnings
app.secret_key = 'secret_key'

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="http://127.0.0.1:5500")
CORS(app, origins=["http://127.0.0.1:5500"], supports_credentials=True)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))


class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(200), nullable=True)  # Make image optional
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, title, price, location, description, image, user_id):
        self.title = title
        self.price = price
        self.location = location
        self.description = description
        self.image = image
        self.user_id = user_id


# Routes
@app.route('/')
def index():
    return redirect('/login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirmpassword = request.form['confirmpassword']

        if password != confirmpassword:
            return render_template('register.html', error="Passwords do not match.")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Email already exists.")

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        return redirect('/http://127.0.0.1:5500/login.html')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Invalid email or password.')
    return render_template('login.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # Check if user is logged in (session contains user_id)
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])  # Retrieve user by session ID
    properties = Property.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        title = request.form['title']
        price = request.form['price']
        location = request.form['location']
        description = request.form['description']
        amenities = request.form.getlist('amenities')
        image = request.files.get('image')  # Image is now optional

        image_filename = None
        if image:
            if not os.path.exists('static/uploads'):
                os.makedirs('static/uploads')
            image_filename = f"static/uploads/{image.filename}"
            image.save(image_filename)

        new_property = Property(
            title=title,
            price=price,
            location=location,
            description=description,
            image=image_filename if image else None,
            user_id=user.id
        )
        db.session.add(new_property)
        db.session.commit()

        # Emit event to frontend for new property
        socketio.emit('new_property', {
            'title': title,
            'price': price,
            'location': location,
            'description': description,
            'image': image_filename if image else None
        }, broadcast=True)

        return redirect('/dashboard')

    return render_template('dashboard.html', user=user, properties=properties)


@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user_id from the session
    return redirect('http://127.0.0.1:5500/login.html')  # Redirect to frontend login page



# Start the socketio server
if __name__ == '__main__':
    socketio.run(app, debug=True)
