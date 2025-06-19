import pandas as pd
import firebase_admin
from firebase_admin import credentials, auth
from flask import Flask, request, render_template_string, send_file, abort
import os
import urllib.parse
import logging
import re

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define HTML templates
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>College Predictor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .form-container { max-width: 600px; margin: auto; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        select, input[type="number"], input[type="submit"] {
            width: 100%; padding: 8px; margin-top: 5px; }
        .error { color: red; }
    </style>
</head>
<body>
    <div class="form-container">
        <h1>College Predictor</h1>
        <form method="POST" action="/predict">
            <div class="form-group">
                <label for="rank">Enter Your Rank:</label>
                <input type="number" id="rank" name="rank" value="{{ form_data.get('rank', '') }}" required>
            </div>
            <div class="form-group">
                <label for="program">Program:</label>
                <select id="program" name="program">
                    <option value="Any" {% if form_data.get('program') == 'Any' %}selected{% endif %}>Any</option>
                    {% for program in programs %}
                        <option value="{{ program }}" {% if form_data.get('program') == program %}selected{% endif %}>{{ program }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="stream">Stream:</label>
                <select id="stream" name="stream">
                    <option value="Any" {% if form_data.get('stream') == 'Any' %}selected{% endif %}>Any</option>
                    {% for stream in streams %}
                        <option value="{{ stream }}" {% if form_data.get('stream') == stream %}selected{% endif %}>{{ stream }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="category">Category:</label>
                <select id="category" name="category">
                    <option value="Any" {% if form_data.get('category') == 'Any' %}selected{% endif %}>Any</option>
                    {% for category in categories %}
                        <option value="{{ category }}" {% if form_data.get('category') == category %}selected{% endif %}>{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="quota">Quota:</label>
                <select id="quota" name="quota">
                    <option value="Any" {% if form_data.get('quota') == 'Any' %}selected{% endif %}>Any</option>
                    {% for quota in quotas %}
                        <option value="{{ quota }}" {% if form_data.get('quota') == quota %}selected{% endif %}>{{ quota }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="seat_type">Seat Type:</label>
                <select id="seat_type" name="seat_type">
                    <option value="Any" {% if form_data.get('seat_type') == 'Any' %}selected{% endif %}>Any</option>
                    {% for seat_type in seat_types %}
                        <option value="{{ seat_type }}" {% if form_data.get('seat_type') == seat_type %}selected{% endif %}>{{ seat_type }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="round">Round:</label>
                <select id="round" name="round">
                    <option value="Any" {% if form_data.get('round') == 'Any' %}selected{% endif %}>Any</option>
                    {% for round in rounds %}
                        <option value="{{ round }}" {% if form_data.get('round') == round %}selected{% endif %}>{{ round }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="year">Year:</label>
                <select id="year" name="year">
                    <option value="Any" {% if form_data.get('year') == 'Any' %}selected{% endif %}>Any</option>
                    {% for year in years %}
                        <option value="{{ year }}" {% if form_data.get('year') == year %}selected{% endif %}>{{ year }}</option>
                    {% endfor %}
                </select>
            </div>
            <input type="submit" value="Predict Colleges">
        </form>
    </div>
</body>
</html>
"""

RESULTS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prediction Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .results-container { max-width: 800px; margin: auto; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .message { color: red; margin: 10px 0; }
        .pagination { margin-top: 20px; }
        .pagination a { margin: 0 5px; text-decoration: none; }
        .download-btn { margin-top: 10px; display: inline-block; padding: 10px; background-color: #4CAF50; color: white; text-decoration: none; }
    </style>
</head>
<body>
    <div class="results-container">
        <h1>College Prediction Results</h1>
        {% if low_rank_message %}
            <p class="message">{{ low_rank_message }}</p>
        {% endif %}
        {% if min_rank_message %}
            <p class="message">{{ min_rank_message }}</p>
        {% endif %}
        <p>Total Results: {{ total_results }}</p>
        <table>
            <thead>
                <tr>
                    <th>Institute</th>
                    <th>Program</th>
                    <th>Round</th>
                    <th>Category</th>
                    <th>Quota</th>
                    <th>Seat Type</th>
                    <th>Opening Rank</th>
                    <th>Closing Rank</th>
                    <th>Year</th>
                </tr>
            </thead>
            <tbody>
                {% for result in results %}
                    <tr>
                        <td>{{ result['Institute'] }}</td>
                        <td>{{ result['Program'] }}</td>
                        <td>{{ result['Round'] }}</td>
                        <td>{{ result['Category'] }}</td>
                        <td>{{ result['Quota'] }}</td>
                        <td>{{ result['Seat Type'] }}</td>
                        <td>{{ result['Opening Rank'] }}</td>
                        <td>{{ result['Closing Rank'] }}</td>
                        <td>{{ result['Year'] }}</td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
        <div class="pagination">
            {% if page > 1 %}
                <a href="/predict?rank={{ form_data.get('rank') }}&program={{ form_data.get('program') }}&stream={{ form_data.get('stream') }}&category={{ form_data.get('category') }}&quota={{ form_data.get('quota') }}&seat_type={{ form_data.get('seat_type') }}&round={{ form_data.get('round') }}&year={{ form_data.get('year') }}&page={{ page - 1 }}">Previous</a>
            {% endif %}
            {% if has_next %}
                <a href="/predict?rank={{ form_data.get('rank') }}&program={{ form_data.get('program') }}&stream={{ form_data.get('stream') }}&category={{ form_data.get('category') }}&quota={{ form_data.get('quota') }}&seat_type={{ form_data.get('seat_type') }}&round={{ form_data.get('round') }}&year={{ form_data.get('year') }}&page={{ page + 1 }}">Next</a>
            {% endif %}
        </div>
        <a href="/download" class="download-btn">Download Results as CSV</a>
        <p><a href="/">Back to Predictor</a></p>
    </div>
</body>
</html>
"""

# Load and preprocess data
data_file_path = 'wbjee_final_clean.xls'  # Local relative path
if os.environ.get('RENDER', 'False') == 'True':
    data_file_path = '/app/data/wbjee_final_clean.xls'  # Render disk path
data = pd.read_csv(data_file_path)

# Handle missing values
data['Seat Type'] = data['Seat Type'].fillna('Unknown')
data['Stream'] = data['Stream'].fillna('Unknown')
data['Program'] = data['Program'].fillna('Unknown')
data['Category'] = data['Category'].fillna('Unknown')

# Normalize columns
for col in ['Program', 'Institute', 'Category', 'Quota', 'Round', 'Seat Type']:
    data[col] = data[col].str.strip().str.title().str.replace('  ', ' ').str.replace('&', 'And')
data['Stream'] = data['Stream'].str.strip().str.replace(r'[./]', '/', regex=True).str.replace('  ', ' ').str.title()
data['Category'] = data['Category'].str.replace('Obc - A', 'Obc-A').str.replace('Obc - B', 'Obc-B')
data['Program'] = data['Program'].str.replace(r'\s*\(.*\)', '', regex=True)
data['Year'] = pd.to_numeric(data['Year'], errors='coerce').fillna(0).astype(int)
data = data.drop_duplicates()

# Verify data
logger.debug(f"Columns: {data.columns.tolist()}")
logger.debug(f"Unique Years: {data['Year'].unique()}")
logger.debug(f"Unique Seat Types: {data['Seat Type'].unique()}")
logger.debug(f"Unique Categories: {data['Category'].unique()}")
logger.debug(f"Unique Programs: {data['Program'].unique()}")
logger.debug(f"Unique Streams: {data['Stream'].unique()}")

# Initialize Firebase Admin SDK with environment variable
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_CONFIG')
    if firebase_config:
        import json
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        raise ValueError("FIREBASE_CONFIG environment variable not set")
    firebase_admin.initialize_app(cred)

# Email validation function (only Gmail addresses)
def is_valid_gmail(email):
    gmail_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(gmail_pattern, email) is not None

# Middleware to verify Firebase ID token
def verify_token():
    id_token = request.headers.get('Authorization')
    if not id_token:
        logger.error("No token provided")
        abort(401, description="Unauthorized: No token provided")
    try:
        if id_token.startswith('Bearer '):
            id_token = id_token.split(' ')[1]
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        abort(401, description=f"Unauthorized: Invalid token - {str(e)}")

@app.route('/')
def home():
    programs = sorted([x for x in data['Program'].unique() if pd.notna(x) and x != 'Unknown'])
    streams = sorted([x for x in data['Stream'].unique() if pd.notna(x) and x != 'Unknown'])
    categories = sorted([x for x in data['Category'].unique() if pd.notna(x) and x != 'Unknown'])
    quotas = sorted([x for x in data['Quota'].unique() if pd.notna(x)])
    seat_types = sorted([x for x in data['Seat Type'].unique() if pd.notna(x) and x != 'Unknown'])
    rounds = sorted([x for x in data['Round'].unique() if pd.notna(x)])
    years = sorted([x for x in data['Year'].unique() if x != 0])
    form_data = {k: urllib.parse.unquote(v) for k, v in request.args.items()}
    return render_template_string(INDEX_HTML, programs=programs, streams=streams, categories=categories,
                                 quotas=quotas, seat_types=seat_types, rounds=rounds, years=years, form_data=form_data)

@app.route('/predictor')
def predictor():
    programs = sorted([x for x in data['Program'].unique() if pd.notna(x) and x != 'Unknown'])
    streams = sorted([x for x in data['Stream'].unique() if pd.notna(x) and x != 'Unknown'])
    categories = sorted([x for x in data['Category'].unique() if pd.notna(x) and x != 'Unknown'])
    quotas = sorted([x for x in data['Quota'].unique() if pd.notna(x)])
    seat_types = sorted([x for x in data['Seat Type'].unique() if pd.notna(x) and x != 'Unknown'])
    rounds = sorted([x for x in data['Round'].unique() if pd.notna(x)])
    years = sorted([x for x in data['Year'].unique() if x != 0])
    form_data = {k: urllib.parse.unquote(v) for k, v in request.args.items()}
    return render_template_string(INDEX_HTML, programs=programs, streams=streams, categories=categories,
                                 quotas=quotas, seat_types=seat_types, rounds=rounds, years=years, form_data=form_data)

@app.route('/predict', methods=['POST', 'GET'])
def predict():
    try:
        decoded_token = verify_token()
        logger.debug(f"Authenticated user: {decoded_token.get('email')}")
        if request.method == 'POST':
            form_data = request.form.to_dict()
        else:
            form_data = {k: urllib.parse.unquote(v) for k, v in request.args.items()}
        rank = int(form_data.get('rank', 0))
        program = form_data.get('program', 'Any')
        stream = form_data.get('stream', 'Any')
        category = form_data.get('category', 'Any')
        quota = form_data.get('quota', 'Any')
        seat_type = form_data.get('seat_type', 'Any')
        round = form_data.get('round', 'Any')
        year = form_data.get('year', 'Any')
        logger.debug(f"Input: rank={rank}, program={program}, stream={stream}, category={category}, quota={quota}, seat_type={seat_type}, round={round}, year={year}")
        page = int(form_data.get('page', 1))
        per_page = 20
        filtered_data = data.copy()
        low_rank_message = None
        min_rank_message = None
        temp_data = filtered_data.copy()
        if program != 'Any':
            logger.debug(f"Applying program filter: {program}")
            temp_data = temp_data[temp_data['Program'] == program]
            logger.debug(f"After program filter, rows: {len(temp_data)}")
        if stream != 'Any':
            logger.debug(f"Applying stream filter: {stream}")
            temp_data = temp_data[temp_data['Stream'] == stream]
            logger.debug(f"After stream filter, rows: {len(temp_data)}")
        if category != 'Any':
            logger.debug(f"Applying category filter: {category}")
            temp_data = temp_data[temp_data['Category'] == category]
            logger.debug(f"After category filter, rows: {len(temp_data)}")
        if quota != 'Any':
            logger.debug(f"Applying quota filter: {quota}")
            temp_data = temp_data[temp_data['Quota'] == quota]
            logger.debug(f"After quota filter, rows: {len(temp_data)}")
        if seat_type != 'Any':
            logger.debug(f"Applying seat_type filter: {seat_type}")
            temp_data = temp_data[temp_data['Seat Type'] == seat_type]
            logger.debug(f"After seat_type filter, rows: {len(temp_data)}")
        if round != 'Any':
            logger.debug(f"Applying round filter: {round}")
            temp_data = temp_data[temp_data['Round'] == round]
            logger.debug(f"After round filter, rows: {len(temp_data)}")
        if year != 'Any':
            logger.debug(f"Applying year filter: {year}")
            temp_data = temp_data[temp_data['Year'] == int(year)]
            logger.debug(f"After year filter, rows: {len(temp_data)}")
        if temp_data.empty or 'Opening Rank' not in temp_data.columns:
            min_rank_message = "No colleges found for these filters. Try relaxing filters like Stream, Program, Category, or Year."
            if stream != 'Any':
                logger.debug(f"Retrying without stream filter: {stream}")
                temp_data = filtered_data.copy()
                if program != 'Any':
                    temp_data = temp_data[temp_data['Program'] == program]
                if category != 'Any':
                    temp_data = temp_data[temp_data['Category'] == category]
                if quota != 'Any':
                    temp_data = temp_data[temp_data['Quota'] == quota]
                if seat_type != 'Any':
                    temp_data = temp_data[temp_data['Seat Type'] == seat_type]
                if round != 'Any':
                    temp_data = temp_data[temp_data['Round'] == round]
                if year != 'Any':
                    temp_data = temp_data[temp_data['Year'] == int(year)]
                min_rank_message += f" Showing results without Stream filter."
            filtered_data = pd.DataFrame(columns=data.columns) if temp_data.empty else temp_data
            logger.debug("No results after applying filters or missing 'Opening Rank' column")
        else:
            min_opening_rank = temp_data['Opening Rank'].min()
            max_opening_rank = temp_data['Opening Rank'].max()
            logger.debug(f"Min opening rank: {min_opening_rank}, Max opening rank: {max_opening_rank}")
            filtered_data = temp_data[
                (temp_data['Opening Rank'] <= rank) &
                (temp_data['Closing Rank'] >= rank)
            ]
            if filtered_data.empty:
                min_rank_message = f"No colleges found for rank {rank}. Showing colleges with opening ranks above or below your rank."
                filtered_data = temp_data.copy()
                filtered_data['Rank_Diff'] = abs(filtered_data['Opening Rank'] - rank)
                filtered_data = filtered_data.sort_values('Rank_Diff').drop(columns=['Rank_Diff'])
                logger.debug(f"Showing {len(filtered_data)} colleges with ranks above/below")
        if not filtered_data.empty and not min_rank_message and len(filtered_data) < 10:
            low_rank_message = f"Showing additional colleges to provide more options."
            filtered_data = temp_data.copy()
            filtered_data['Rank_Diff'] = abs(filtered_data['Opening Rank'] - rank)
            filtered_data = filtered_data.sort_values('Rank_Diff').drop(columns=['Rank_Diff'])
            logger.debug(f"Expanded results, rows: {len(filtered_data)}")
        if min_rank_message or low_rank_message:
            filtered_data = filtered_data.sort_values('Opening Rank')
        else:
            filtered_data = filtered_data.sort_values('Closing Rank')
        results_file_path = 'results.csv'  # Local relative path
        if os.environ.get('RENDER', 'False') == 'True':
            results_file_path = '/app/data/results.csv'  # Render disk path
        filtered_data.to_csv(results_file_path, index=False)
        total_results = len(filtered_data)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = filtered_data.iloc[start:end][['Institute', 'Program', 'Round', 'Category', 'Quota', 'Seat Type', 'Opening Rank', 'Closing Rank', 'Year']].to_dict('records')
        has_next = end < total_results
        return render_template_string(RESULTS_HTML, results=paginated_results, rank=rank, page=page, has_next=has_next,
                                     total_results=total_results, form_data=form_data, low_rank_message=low_rank_message,
                                     min_rank_message=min_rank_message)
    except Exception as e:
        logger.error(f"Error in predict: {str(e)}")
        abort(500, description=f"Error: {str(e)}")

@app.route('/download')
def download():
    try:
        verify_token()
        results_file_path = 'results.csv'  # Local relative path
        if os.environ.get('RENDER', 'False') == 'True':
            results_file_path = '/app/data/results.csv'  # Render disk path
        return send_file(results_file_path, as_attachment=True, download_name='college_results.csv')
    except Exception as e:
        logger.error(f"Error in download: {str(e)}")
        abort(500, description=f"Error: No results to download. {str(e)}")

@app.route('/favicon.ico')
def favicon():
    try:
        return send_file('static/favicon.ico')
    except FileNotFoundError:
        abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))