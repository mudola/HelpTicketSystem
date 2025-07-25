from flask_wtf import FlaskForm # type: ignore
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, PasswordField, BooleanField, IntegerField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp, NumberRange
from models import User, Category

class LoginForm(FlaskForm):
    username = StringField('Payroll Number', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Payroll number must be exactly 6 digits'),
        Regexp('^[0-9]{6}$', message='Payroll number must be exactly 6 digits')
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Username must be exactly 6 digits'),
        Regexp('^[0-9]{6}$', message='Username must be exactly 6 digits')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    phone_number = StringField('Phone Number', validators=[
        Optional(),
        Regexp(r'^[\+]?[1-9][\d]{0,15}$', message='Please enter a valid phone number')
    ])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('user', 'User'), ('intern', 'Intern')], default='user')
    submit = SubmitField('Register')

    def validate(self, extra_validators=None):
        initial = super().validate(extra_validators)
        # Allow intern registration with default credentials
        if self.username.data == 'dctraining' and self.password.data == 'Dctraining2023':
            return True
        return initial

class TicketForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
    location_unit = SelectField('Unit', choices=[
        ('', 'Select Unit'),
        ('SWA', 'SWA'),
        ('UHS', 'UHS'),
        ('Confucius', 'Confucius')
    ])
    location_subunit = SelectField('Subunit', choices=[('', 'Select Subunit')], validate_choice=False)
    location_detail = SelectField('Location Detail', choices=[('', 'Select Location')], validate_choice=False)
    description = TextAreaField('Description', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[Optional()])
    mis_subcategory = StringField('MIS Subcategory')
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')
    assignees = SelectMultipleField('Assign To', coerce=int, validators=[Optional()])
    attachments = FileField('Attachments', validators=[
        FileAllowed(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'], 
                   'Only text, PDF, image, and document files are allowed!')
    ])
    submit = SubmitField('Submit Ticket')

    def __init__(self, *args, **kwargs):
        super(TicketForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(0, 'Select Category')] + [(c.id, c.name) for c in Category.query.all()]
        self.assignees.choices = [(u.id, u.full_name) for u in User.query.filter(User.role.in_(['admin', 'intern'])).all()]

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    is_internal = BooleanField('Internal Comment (Only visible to Admin and Interns)')
    submit = SubmitField('Add Comment')

class TicketUpdateForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ])
    assignees = SelectMultipleField('Assignees', coerce=int, validators=[Optional()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ])
    submit = SubmitField('Update Ticket')

    def __init__(self, user_role=None, current_status=None, *args, **kwargs):
        super(TicketUpdateForm, self).__init__(*args, **kwargs)
        self.assignees.choices = [(u.id, u.full_name) for u in User.query.filter(User.role.in_(['admin', 'intern'])).all()]

        # Restrict status choices for interns
        if user_role == 'intern':
            if current_status == 'resolved':
                # Once resolved, interns can only keep it resolved or closed (but closed is also restricted)
                self.status.choices = [('resolved', 'Resolved')]
            else:
                # Normal progression for interns
                self.status.choices = [
                    ('open', 'Open'),
                    ('in_progress', 'In Progress'),
                    ('resolved', 'Resolved')
                ]

class UserManagementForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Update Password')

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=50)])
    description = StringField('Description', validators=[Length(max=200)])
    submit = SubmitField('Add Category')

class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

class AdminUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[('user', 'User'), ('intern', 'Intern'), ('admin', 'Admin')], default='user')
    submit = SubmitField('Create User')

class UserStatusForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    is_active = BooleanField('Active Status')
    submit = SubmitField('Update Status')

class NotificationSettingsForm(FlaskForm):
    new_ticket_email = BooleanField('New ticket email notifications')
    new_ticket_app = BooleanField('New ticket in-app notifications')
    ticket_updated_email = BooleanField('Ticket updated email notifications')
    ticket_updated_app = BooleanField('Ticket updated in-app notifications')
    new_comment_email = BooleanField('New comment email notifications')
    new_comment_app = BooleanField('New comment in-app notifications')
    ticket_closed_email = BooleanField('Ticket closed email notifications')
    ticket_closed_app = BooleanField('Ticket closed in-app notifications')
    ticket_overdue_email = BooleanField('Overdue ticket email notifications')
    ticket_overdue_app = BooleanField('Overdue ticket in-app notifications')
    do_not_disturb = BooleanField('Enable Do Not Disturb')
    dnd_start_time = StringField('DND Start Time')
    dnd_end_time = StringField('DND End Time')
    submit = SubmitField('Save Settings')