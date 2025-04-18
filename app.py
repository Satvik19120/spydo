from flask import Flask, render_template,send_file, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import io
import matplotlib
matplotlib.use("Agg")  # Set the backend to "Agg"
import matplotlib.pyplot as plt  # Now you can import pyplot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'm1n0r_pr0ject'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minor_proj.db'
app.app_context().push()
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # sponsor, influencer
    plateforms=db.Column(db.String(50), default="")#------for influencer
    followers=db.Column(db.String(50), default="")#--------for influencer
    is_blocked=db.Column(db.Boolean, default=False)#-------for influencer

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    budget = db.Column(db.Float, nullable=False)
    visibility = db.Column(db.String(50), nullable=False)  # public or private
    goals = db.Column(db.String(150), nullable=False)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sponsor = db.relationship('User', foreign_keys=[sponsor_id])

    # Add a new field to store selected influencers for private campaigns
    selected_influencers = db.Column(db.String, default="")  # Comma separated list of influencer IDs


class AdRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    influencer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sponser_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=False)
    payment_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # Pending, Accepted, Rejected
    campaign = db.relationship('Campaign', backref='campain')
    customer = db.relationship('User', foreign_keys=[influencer_id])
    sponser = db.relationship('User', foreign_keys=[sponser_id])




# Authentication Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/',host=8000)
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        platforms = request.form.get('platforms')
        followers = request.form.get('followers')

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        # Simple form validation
        if not username or not password or not role:
            flash('Please fill in all required fields.', 'danger')
            return render_template('register.html')

        
        hashed_password = (password)

        # Create a new user object
        new_user = User(username=username, password=hashed_password, role=role)

        # If the role is 'influencer', add the platforms and followers data
        if role == 'influencer':
            if not platforms or not followers:
                flash('Please provide platforms and followers for influencers.', 'danger')
                return render_template('register.html')
            new_user.plateforms = platforms
            new_user.followers = followers

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))  # Redirect to login page after successful registration
        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            flash(f'Error occurred: {str(e)}', 'danger')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Get the user from the database by username
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:  # Directly compare plain text passwords
            login_user(user)
            
            # Check if the user is blocked
            if user.is_blocked:
                flash('Your account has been blocked. Please contact support.')
                return redirect(url_for('login'))
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'sponsor':
                return redirect(url_for('sponsor_dashboard'))
            elif user.role == 'influencer':
                return redirect(url_for('influencer_dashboard'))
        else:
            flash('Login failed. Check your credentials and try again.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Admin Routes
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # Ensure only admins can access
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    # Fetch necessary data for the dashboard
    total_users = User.query.count()-1
    total_campaigns = Campaign.query.count()
    total_ad_requests = AdRequest.query.count()

    # Get flagged users (e.g., users who are blocked)
    flagged_users = User.query.filter_by(is_blocked=True).all()

    # Get all users (for blocking/unblocking)
    users = User.query.filter(User.role != 'admin').all()


    # Get flagged campaigns (assuming some flagging system is in place)
    flagged_campaigns = Campaign.query.filter_by(visibility='private').all()

    return render_template('admin_dashboard.html',
                        total_users=total_users,
                        total_campaigns=total_campaigns,
                        total_ad_requests=total_ad_requests,
                        flagged_users=flagged_users,
                        flagged_campaigns=flagged_campaigns,
                        users=users)


# Route to display users
@app.route('/admin/users')
@login_required
def view_users():
    # Only allow admins to view this page
    if current_user.role != 'admin':
        return redirect(url_for('home'))  # or any other page if user is not admin
    
    # Fetch all users from the database
    users = User.query.filter(User.role!='admin').all()
    return render_template('view_users.html', users=users)

# Route to block a user
@app.route('/admin/block/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))  # If not admin, redirect to home
    
    user = User.query.get(user_id)
    if user:
        user.is_blocked = True # Block the user
        db.session.commit()
        return redirect(url_for('admin_dashboard'))  # Redirect back to user list
    return redirect(url_for('admin_dashboard'))  # Redirect if user not found

# Route to unblock a user
@app.route('/admin/unblock/<int:user_id>', methods=['POST'])
@login_required
def unblock_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))  # If not admin, redirect to home
    
    user = User.query.get(user_id)
    if user:
        user.is_blocked = False # Block the user
        db.session.commit()
        return redirect(url_for('admin_dashboard'))  # Redirect back to user list
    return redirect(url_for('admin_dashboard'))  # Redirect if user not found

@app.route('/flag_campaign/<int:campaign_id>')
@login_required
def flag_campaign(campaign_id):
    # Example: Implement flagging logic
    #flash('Campaign flagged successfully.')
    return redirect(url_for('admin_dashboard'))













#-------------------------Sponsor Routes--------------------------

@app.route('/sponsor_dashboard')
@login_required
def sponsor_dashboard():
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))  # Redirect to home if the user is not a sponsor
    
    
    
    # Fetch influencers that are not blocked
    influencers = User.query.filter_by(role='influencer', is_blocked=False).all()
    # Fetch campaigns that belong to the logged-in sponsor
    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    # Fetch ad requests for campaigns that belong to the logged-in sponsor
    ad_requests = AdRequest.query.join(Campaign).filter(Campaign.sponsor_id == current_user.id).all()

    return render_template('sponsor_dashboard.html',campaigns=campaigns,ad_requests=ad_requests,influencers=influencers)




@app.route('/create_campaign', methods=['GET', 'POST'])
@login_required
def create_campaign():
    if current_user.role != 'sponsor':
        flash('Only sponsors can create campaigns.', 'danger')
        return redirect(url_for('home'))  # Redirect to a home or dashboard page
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        budget = request.form['budget']
        goals = request.form['goals']
        visibility='public'
        # Convert the string dates into datetime.date objects
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError as e:
            flash(f"Error parsing date: {e}", 'danger')
            return redirect(url_for('create_campaign'))  # Redirect if date parsing fails

        # Get the selected influencers for private campaigns
        selected_influencers = request.form.getlist('influencers')

        # Create the campaign object
        campaign = Campaign(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            visibility=visibility,
            goals=goals,
            sponsor_id=current_user.id  # Linking to the sponsor
        )

        # If the campaign is private, store the selected influencers as a comma-separated list
        if visibility == 'private' and selected_influencers:
            campaign.selected_influencers = ",".join(selected_influencers)

        # Add the campaign to the database
        db.session.add(campaign)
        db.session.commit()

        #flash('Campaign created successfully!', 'success')
        return redirect(url_for('sponsor_dashboard'))  # Redirect to sponsor dashboard or campaign list

    # Fetch all influencers who are not blocked to display in the form (for private campaigns)
    influencers = User.query.filter_by(role='influencer', is_blocked=False).all()

    return render_template('create_campaign.html', influencers=influencers)


@app.route('/view_campaign/<int:campaign_id>', methods=['GET'])
def view_campaign(campaign_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))
    
    # Fetch campaign details from the database
    campaign = Campaign.query.get_or_404(campaign_id)

    # Ensure that the current user is the sponsor of the campaign
    if campaign.sponsor_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))
    
    return render_template('view_campaign.html', campaign=campaign)



@app.route('/edit_campaign/<int:campaign_id>', methods=['GET', 'POST'])
@login_required
def edit_campaign(campaign_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))
    
    # Retrieve the campaign by ID
    campaign = Campaign.query.get_or_404(campaign_id)

    # Make sure the campaign belongs to the current sponsor
    if campaign.sponsor_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))

    if request.method == 'POST':
        # Update the campaign details based on the form input
        campaign.name = request.form['name']
        campaign.description = request.form['description']
        campaign.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        campaign.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        campaign.budget = float(request.form['budget'])
        campaign.visibility = 'public'
        campaign.goals = request.form['goals']

        db.session.commit()  # Save the changes to the database
        #flash('Campaign updated successfully!')
        return redirect(url_for('sponsor_dashboard'))  # Redirect to sponsor dashboard

    return render_template('edit_campaign.html', campaign=campaign)


@app.route('/delete_campaign/<int:campaign_id>')
@login_required
def delete_campaign(campaign_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.sponsor_id == current_user.id:
        db.session.delete(campaign)
        db.session.commit()
        #flash('Campaign deleted successfully!')
    else:
        flash('You are not authorized to delete this campaign.')
    return redirect(url_for('sponsor_dashboard'))



@app.route('/view_ad_requests/<int:campaign_id>', methods=['GET'])
def view_ad_requests(campaign_id):
    # Ensure the user is logged in and is a sponsor
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))

    # Fetch the campaign and check if it belongs to the sponsor
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.sponsor_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))

    # Fetch the ad requests for the campaign
    ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()

    return render_template('view_ad_requests.html', campaign=campaign, ad_requests=ad_requests)



@app.route('/accept_ad_request/<int:ad_request_id>', methods=['GET'])
def accept_ad_request(ad_request_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))

    ad_request = AdRequest.query.get_or_404(ad_request_id)

    # Ensure the sponsor owns the campaign
    if ad_request.sponser_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))

    # Change the status to accepted
    ad_request.status = 'accepted'
    db.session.commit()

    #flash('Ad request accepted!', 'success')
    return redirect(url_for('sponsor_dashboard', campaign_id=ad_request.campaign_id))

@app.route('/reject_ad_request/<int:ad_request_id>', methods=['GET'])
def reject_ad_request(ad_request_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))

    ad_request = AdRequest.query.get_or_404(ad_request_id)

    # Ensure the sponsor owns the campaign
    if ad_request.sponser_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))

    # Change the status to rejected
    ad_request.status = 'rejected'
    db.session.commit()

    #flash('Ad request rejected.', 'danger')
    return redirect(url_for('sponsor_dashboard', campaign_id=ad_request.campaign_id))

@app.route('/sponsor/view_campaign_graph/<int:campaign_id>', methods=['GET'])
@login_required
def view_campaign_graph(campaign_id):
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))  # Only sponsors should access this page

    # Fetch the campaign from the database
    campaign = Campaign.query.get_or_404(campaign_id)
    
    # Ensure the campaign belongs to the logged-in sponsor
    if campaign.sponsor_id != current_user.id:
        return redirect(url_for('sponsor_dashboard'))  # Redirect to dashboard if the sponsor does not own the campaign
    
    # Fetch ad requests related to this campaign
    ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()

    # Count the number of requests by status
    accepted_count = sum(1 for request in ad_requests if request.status == 'accepted')
    rejected_count = sum(1 for request in ad_requests if request.status == 'rejected')
    pending_count = sum(1 for request in ad_requests if request.status == 'Pending')

    # Create a bar chart using Matplotlib
    labels = ['Accepted', 'Rejected', 'Pending']
    counts = [accepted_count, rejected_count, pending_count]

    fig, ax = plt.subplots()
    ax.bar(labels, counts, color=['green', 'red', 'yellow'])

    # Add labels and title
    ax.set_ylabel('Number of Requests')
    ax.set_xlabel('Status of Ad Request')
    ax.set_title(f'Ad Requests for Campaign: {campaign.name}')

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Send the plot image as a response
    return send_file(img, mimetype='image/png')

@app.route('/sponsor_summary')
@login_required
def sponsor_summary():
    if current_user.role != 'sponsor':
        return redirect(url_for('index'))  # Redirect to home if the user is not a sponsor
    
    
    
    # Fetch influencers that are not blocked
    #influencers = User.query.filter_by(role='influencer', is_blocked=False).all()
    # Fetch campaigns that belong to the logged-in sponsor
    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    # Fetch ad requests for campaigns that belong to the logged-in sponsor
    #ad_requests = AdRequest.query.join(Campaign).filter(Campaign.sponsor_id == current_user.id).all()

    return render_template('sponsor_summary.html',campaigns=campaigns)






#---------------------- influencer Routes-------------------------------------------------------------
@app.route('/influencer_dashboard')
@login_required
def influencer_dashboard():
    if current_user.role != 'influencer':
        return redirect(url_for('index'))
    ad_requests = AdRequest.query.filter_by(influencer_id=current_user.id).all()
    campaigns = Campaign.query.filter_by(visibility='public').all() 
    return render_template('influencer_dashboard.html',campaigns=campaigns, ad_requests=ad_requests)

@app.route('/search_campaigns', methods=['GET', 'POST'])
def search_campaigns():
    if request.method == 'POST':
        search_query = request.form.get('search', '')  # Use .get() to avoid KeyError
        if search_query:  # If the search query is not empty
            campaigns = Campaign.query.filter(Campaign.name.like(f"%{search_query}%")).all()
        else:
            campaigns = Campaign.query.filter_by(visibility='public').all()  # Default to public campaigns if search is empty
    else:
        campaigns = Campaign.query.filter_by(visibility='public').all()  # Handle GET requests

    return render_template('search_campaigns.html', campaigns=campaigns)


@app.route('/send_ad_request/<int:campaign_id>', methods=['GET', 'POST'])
@login_required
def send_ad_request(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if current_user.role != 'influencer':
        return redirect(url_for('index'))

    if request.method == 'POST':
        message = request.form.get('message')
        requirements = request.form['requirements']
        payment_amount = float(request.form['payment_amount'])
        
        # Create the ad request and associate it with the influencer and sponsor
        ad_request = AdRequest(
            campaign_id=campaign.id,
            influencer_id=current_user.id,
            sponser_id=campaign.sponsor_id,  # Assuming campaign has a sponsor_id field
            messages=message,
            requirements=requirements,
            payment_amount=payment_amount,
            status='Pending'  # Initial status is set to 'Pending'
        )

        db.session.add(ad_request)
        db.session.commit()

        #flash('Ad request sent successfully!')
        return redirect(url_for('influencer_dashboard'))  # Redirect back to influencer dashboard

    return render_template('send_ad_request.html', campaign=campaign)

@app.route('/influencer/summary', methods=['GET'])
@login_required
def influencer_summary():
    return render_template('influencer_summary.html')
@app.route('/influencer/graph', methods=['GET'])
@login_required
def influencer_graph():
    # Make sure the user is an influencer
    if current_user.role != 'influencer':
        flash("Only influencers can access this page", 'danger')
        return redirect(url_for('index'))
    
    # Query to count the number of ad requests by status
    accepted_count = AdRequest.query.filter_by(influencer_id=current_user.id, status='accepted').count()
    rejected_count = AdRequest.query.filter_by(influencer_id=current_user.id, status='rejected').count()
    pending_count = AdRequest.query.filter_by(influencer_id=current_user.id, status='Pending').count()

    # Create a bar chart using Matplotlib
    labels = ['Accepted', 'Rejected', 'Pending']
    counts = [accepted_count, rejected_count, pending_count]

    fig, ax = plt.subplots()
    ax.bar(labels, counts, color=['green', 'red', 'yellow'])

    # Add labels and title
    ax.set_ylabel('Number of Requests')
    ax.set_xlabel('Status of ad request')
    ax.set_title(f'Ad Requests tracking')

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Send the plot image as a response
    #return render_template('influencer_summary.html', graph_image=img)
    return send_file(img, mimetype='image/png')



@app.route('/ad_request_detail/<int:ad_request_id>')
@login_required
def ad_request_detail(ad_request_id):
    ad_request = AdRequest.query.get_or_404(ad_request_id)
    return render_template('ad_request_detail.html', ad_request=ad_request)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
