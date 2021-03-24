# app.py
import json
from uuid import uuid4
from flask import Flask, abort, redirect, url_for, g
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired
from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history

app = Flask(__name__, template_folder='./templates')
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = "randomkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(80), nullable=False)
    history = db.Column(db.Text(), nullable=True)
    model_name = db.Column(db.String(80), nullable=False)
    original_id = db.Column(db.Integer)
    db_event_name = db.Column(db.String(80), nullable=False)


class UserForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])


@app.before_request
def before_request_handler():
    g.request_id = uuid4()


@event.listens_for(db.session, 'after_flush')
def db_after_flush(session, flush_context):
    for instance in session.new:
        if isinstance(instance, AuditLog):
            continue
        al = AuditLog(request_id=str(g.request_id), model_name="user",
                      original_id=instance.id,  db_event_name="create")
        session.add(al)


@event.listens_for(db.session, 'before_flush')
def db_before_flush(session, flush_context, instances):
    for instance in session.dirty:
        if isinstance(instance, AuditLog):
            continue
        if isinstance(instance, User):
            history = {}
            if get_history(instance, 'first_name').deleted:
                history['first_name'] = get_history(
                    instance, 'first_name').deleted[0]
            if get_history(instance, 'last_name').deleted:
                history['last_name'] = get_history(
                    instance, 'last_name').deleted[0]
            if len(history):
                al = AuditLog(request_id=str(g.request_id), model_name="user",
                              original_id=instance.id,  db_event_name="edit", history=json.dumps(history))
                session.add(al)
    for instance in session.deleted:
        if isinstance(instance, AuditLog):
            continue
        if isinstance(instance, User):
            history = {
                'first_name': get_history(instance, 'first_name').unchanged[0],
                'last_name':  get_history(instance, 'last_name').unchanged[0]
            }
            if len(history):
                al = AuditLog(request_id=str(g.request_id), model_name="user",
                              original_id=instance.id,  db_event_name="delete", history=json.dumps(history))
                session.add(al)


@app.route('/')
def index():
    users = User.query.all()
    return render_template('index.html', users=users)


@app.route('/create', methods=['GET', 'POST'])
def create():
    userCreateForm = UserForm()
    if userCreateForm.validate_on_submit():
        user = User(first_name=userCreateForm.first_name.data,
                    last_name=userCreateForm.last_name.data)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('.index'))
    return render_template('create.html', form=userCreateForm)


@app.route('/edit/<user_id>', methods=['GET', 'POST'])
def edit(user_id):
    user = User.query.get(user_id)
    if not user:
        abort(404)
    userEditForm = UserForm(first_name=user.first_name,
                            last_name=user.last_name)
    if userEditForm.validate_on_submit():
        user.first_name = userEditForm.first_name.data
        user.last_name = userEditForm.last_name.data
        db.session.commit()
        return redirect(url_for('.index'))
    return render_template('edit.html', form=userEditForm)
