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

# HTML templates (unchanged, using your provided INDEX_HTML and RESULTS_HTML)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))