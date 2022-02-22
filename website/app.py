from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from forms import LoginForm, SignupForm, EditProfileForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from wtforms.validators import ValidationError
from config import Config
from datetime import datetime
# add for thingspeak communication
import urllib
from bs4 import BeautifulSoup
import re # for regex
from flask_mail import Mail
import queue
from queue import Empty

import random
import numpy as np
from datetime import datetime
import time
import json
import csv
import pandas as pd
from pandas import DataFrame
from io import StringIO

app = Flask(__name__)
app.config.from_object(Config)
login = LoginManager(app)
login.login_view = 'login'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

'''
    if packet_queue.empty():
        packet_queue = fill_queue(user, packet_queue)                    # complete initial queue fill
        flash('packet queue was filled')
'''
packet_queue = queue.Queue()

# admin class to store admin users 
class people():
    people = ['Samuel Awuah', 'Shujian Lao', 'Will J Lee', 'Christin Lin', 'Mino Song', 'Noah S Staveley']
    usernames = ['samuel_awuah, shujian_lao', 'will_lee', 'christin_lin', 'mino_song', 'noah_s', '_admin_']
    def __repr__(self):
        return 'People {}>'.format(self.people)

# User class for db
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)          # email field format is validated
    DOB = db.Column(db.String(6), index=True, unique=True)              # DOB field format is validated
    password_hash = db.Column(db.String(128))
    packets = db.relationship("Packet", backref='author', lazy='dynamic')
    packet_count = db.Column(db.Integer, index=True)                    # TODO: managing the users packet counter
    admin = db.Column(db.Integer, index=True, default=False)

    def __repr__(self):
        self.id = id
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def validate_DOB(self, DOB):
        try:
            datetime.strptime(DOB, '%m-%d-%Y')
        except ValueError:
            raise ValidationError("oops, we want your DOB in a specific format. Please try again.")
    
    def validate_email(self, email):
        # regular expression for validating an Email
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if(re.fullmatch(regex, email)):
            pass
        else:
            raise ValidationError("oops, please enter a valid email")
    
    def set_admin(self, username):
        user = User.query.filter_by(username=username).first()
        try: 
            people.usernames.index(username)
            if SignupForm.admin_code == people.usernames:
                self.admin = True
            else:
                self.admin = False
        except ValueError:
            self.admin = False

# packet class for db
class Packet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)         # this timestamp represents when the test was ordered
    test_taken = db.Column(db.String(50), index=True, default=None)                 # this timestamp represents when the test was taken
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_type = db.Column(db.String(150), default=None)

    def __repr__(self):
        self.id = id
        self.user_id = User.id
        return '<Packet {}>'.format(self.body)   
    
# APP ROUTES

# this route loads the user with the given id
@login.user_loader
def load_user(id):
    return User.query.get(int(id))     

# this app route loads the home page 
# you must log in to view the home page 
# right now the home page simply displays a custom greeting for the user
@app.route("/")
@app.route('/index')
@login_required
def index():
    return render_template("index_login.html", title='Home Page')

# home page for guests (not logged in)
@app.route("/")
@app.route('/index_guest')
def index_guest():
    return render_template("index_guest.html", title='Home Page')

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Packet': Packet}

# route for log in page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Log In', form=form)

# log out route 
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


# route for sign up page --> creates new user in database 
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    global packet_queue
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = SignupForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        user.validate_DOB(form.DOB.data)
        user.validate_email(form.email.data)
        user.set_admin(form.username.data)
        user.packet_count = 0
        db.session.add(user)
        db.session.commit()
        MESSAGE = 'Congratulations ' + user.username + ' you are now a registered user!'
        flash(MESSAGE)
        if user.admin == True:
            flash('This is an admin account')
        return redirect(url_for('login'))
    return render_template('signup.html', title='Sign up', form=form)

# this route renders the user profile page 
@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()        
    return render_template('user.html', user=user, packets=user.packets.all()) 

# route for edit profile form 
@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.DOB = form.DOB.data
        current_user.validate_DOB(form.DOB.data)
        current_user.validate_email(form.email.data) 
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.DOB.data = current_user.DOB
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)

# route for the grab new test data button on user profile page    
@app.route('/newtest/<username>')
def newtest(username):
    global packet_queue
    user = User.query.filter_by(username=username).first_or_404()
    
    if (packet_queue.empty()): # if the queue is, first refill then call new packet
        flash('queue was empty when new test was called') # for testing
        packet_queue = fill_queue(user, packet_queue)  
        new_packet(user, packet_queue) # call packet helper w global packet_queue
    else:
        flash('queue was NOT empty when new test was called') # for testing
        new_packet(user, packet_queue) # call packet helper w global packet_queue
    # render user page again with new packet added
    return render_template('user.html', user=user, packets=user.packets.all())

# route for delete all tests button  
@app.route('/deletetests/<username>')
def delete_all_tests(username):
    user = User.query.filter_by(username=username).first_or_404()
    delete_all_packets(user) # call helper function
    return render_template('user.html', user=user, packets=user.packets.all()) 
 
# route for delete this test button
@app.route('/deletetest/<username>/<packet_id>')
def deletetest(username, packet_id):
    user = User.query.filter_by(username=username).first_or_404()
    p = Packet.query.filter_by(id=packet_id).first_or_404()
    #db.session.add(user)
    db.session.delete(p)
    db.session.commit()
    return render_template('user.html', user=user, packets=user.packets.all())  


# this function loops through all the rows in our thingspeak csv table
# and creates a new packet for every row 
# packets are stored in packet_queue and sent to new_packet(user, packet_queue)

# newtest() will call fill_queue whenever packet_queue is empty
# TODO: 
# we only want to add packets with new test result data to the queue 
# update this funciton so that it will disregard rows w that have been grabbed before
#  I plan to do this by storing entry_ids and checking every row's entry id
def fill_queue(user, packet_queue):
    thingspeak_read = urllib.request.urlopen('https://api.thingspeak.com/channels/1649676/feeds.csv?api_key=JLVZFZMPYNBHIU33')
    bytes_csv = thingspeak_read.read()
    data=str(bytes_csv,'utf-8')
    thingspeak_data = pd.read_csv(StringIO(data))
    body_df = pd.DataFrame(thingspeak_data)
    # creates new packet for every row in index and adds packet to our packet_queue 
    for i in range(1,len(body_df.index) +1): 
        this_row = thingspeak_data.iloc[-i] # isolates ith row from the bottom
        test_taken = "Date: "+ str(this_row['field4'])+" Time: "+str(this_row['field5'])
        # create a new packet associated for user 
        p = Packet(body=str(this_row['field3']), author=user, test_type=str(this_row['field2']), test_taken=test_taken) # field2 = test_type
        packet_queue.put(p) # add new packet to our packet_queue
    return packet_queue


def new_packet(user, packet_queue):
    try:
        while True:
            pack = packet_queue.get(block=False)
            done = False
            while not done:
                try:
                    # do stuff
                    # add new packet to db
                    db.session.add(pack)
                    db.session.commit()
                    done = True
                except Exception as e:
                    pass # just try again to do stuff
            packet_queue.task_done()
    except Empty: # no more packets in the queue
        pass
           

# this function deletes all packets for the given user
def delete_all_packets(user):
    packets = user.packets.all() 
    for p in packets:
        # add new packet to db
        db.session.delete(p)
    db.session.commit()

# route for view entire test result 
@app.route('/open_packet/<username>/<packet_id>')
def open_packet(username, packet_id):
    user = User.query.filter_by(username=username).first_or_404()
    #pack = Packet.query.filter_by(id=packet_id).first_or_404()
    return render_template('view_test.html', user=user, packet=Packet.query.get(packet_id))

# route for test visualization/chart page
@app.route('/open_packet/<username>/test_chart')
def test_chart(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('test_chart.html', user=user)


# todo: routes for error handling
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# routes for about page
@app.route('/about')
def about():
    return render_template('about.html', people=people.people)

@app.route('/hardware_team')
def hardware():
    return render_template('hardware_team.html', people=people.people)

@app.route('/software_team')
def software():
    return render_template('software_team.html', people=people.people)

@app.route('/introduction')
def introduction():
    return render_template('introduction.html', people=people.people)

@app.route('/progress')
def progress():
    return render_template('progress.html', people=people.people)
## end about page routes
    
# admin functions - todo 

      
if __name__ == '__main__':
    app.jinja_env.cache = {} # clear cache -> optimize page load time
    app.run(debug=True)
    
    
