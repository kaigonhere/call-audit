import os
import json
from openai import OpenAI
from flask import Flask, request, render_template, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class CallAuditApp:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
    
    def analyze_transcript(self, transcript, criteria=None):
        """Analyze call transcript using OpenAI API."""
        if criteria is None:
            criteria = self.default_criteria()
        
        # Create a prompt for the AI
        prompt = self.create_audit_prompt(transcript, criteria)
        
        # Call the OpenAI API
        response = self.client.chat.completions.create(
            model="gpt-4",  # You can adjust the model based on your needs
            messages=[
                {"role": "system", "content": "You are an expert call center quality analyst. Your task is to analyze customer support call transcripts and provide objective feedback based on the provided criteria."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and return the analysis
        try:
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError:
            return {"error": "Failed to parse API response", "raw_response": response.choices[0].message.content}
    
    def create_audit_prompt(self, transcript, criteria):
        """Create a detailed prompt for the AI to analyze the transcript."""
        prompt = f"""
Please analyze the following customer support call transcript according to these criteria:

{json.dumps(criteria, indent=2)}

Provide a detailed assessment for each criterion with specific examples from the transcript.
For each criterion, provide a score from 1-10 and justify your rating.
Also calculate an overall score and provide a summary of strengths and areas for improvement.

Your response should be in JSON format with the following structure:
{{
    "overall_score": <score>,
    "criteria_scores": {{
        "<criterion_name>": {{
            "score": <score>,
            "assessment": "<detailed assessment>",
            "examples": ["<example from transcript>", ...]
        }},
        ...
    }},
    "strengths": ["<strength 1>", ...],
    "areas_for_improvement": ["<area 1>", ...],
    "summary": "<overall assessment summary>"
}}

Here is the transcript:

{transcript}
"""
        return prompt
    
    def default_criteria(self):
        """Default criteria for call assessment."""
        return {
            "greeting": "Did the agent use a proper greeting and introduce themselves?",
            "listening": "Did the agent actively listen to the customer's concerns?",
            "problem_solving": "Did the agent demonstrate effective problem-solving skills?",
            "knowledge": "Did the agent demonstrate sufficient product/service knowledge?",
            "empathy": "Did the agent show empathy and understanding?",
            "clarity": "Was the agent's communication clear and easy to understand?",
            "resolution": "Did the agent properly resolve the customer's issue?",
            "closing": "Did the agent provide a proper closing to the call?",
            "adherence_to_protocol": "Did the agent follow company protocols and procedures?",
            "professionalism": "Did the agent maintain professionalism throughout the call?"
        }

# Global API key storage
api_key_storage = {}

@app.route('/')
def index():
    """Home page with API key form"""
    return render_template('index.html')

@app.route('/set_api_key', methods=['POST'])
def set_api_key():
    """Save API key to session"""
    api_key = request.form.get('api_key')
    if not api_key:
        return render_template('index.html', error="API key is required")
    
    # Generate a unique ID for this session
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    api_key_storage[session_id] = api_key
    
    return redirect(url_for('audit_form'))

@app.route('/audit')
def audit_form():
    """Form to submit transcript for analysis"""
    if 'session_id' not in session or session['session_id'] not in api_key_storage:
        return redirect(url_for('index'))
    
    return render_template('audit.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Process transcript and return analysis"""
    if 'session_id' not in session or session['session_id'] not in api_key_storage:
        return redirect(url_for('index'))
    
    api_key = api_key_storage[session['session_id']]
    auditor = CallAuditApp(api_key)
    
    # Get transcript either from file upload or text area
    transcript = ""
    if 'transcript_file' in request.files and request.files['transcript_file'].filename:
        file = request.files['transcript_file']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            # Remove the file after reading it
            os.remove(file_path)
    else:
        transcript = request.form.get('transcript_text', '')
    
    if not transcript:
        return render_template('audit.html', error="No transcript provided")
    
    # Get custom criteria if provided
    custom_criteria = {}
    criteria_text = request.form.get('custom_criteria', '')
    if criteria_text:
        try:
            custom_criteria = json.loads(criteria_text)
        except json.JSONDecodeError:
            return render_template('audit.html', error="Invalid JSON format for custom criteria", 
                                  transcript=transcript, custom_criteria=criteria_text)
    
    # Analyze the transcript
    analysis = auditor.analyze_transcript(transcript, custom_criteria if custom_criteria else None)
    
    if 'error' in analysis:
        return render_template('audit.html', error=f"Analysis error: {analysis['error']}", 
                              transcript=transcript, custom_criteria=criteria_text)
    
    # Pass the analysis to the results template
    return render_template('results.html', analysis=analysis, transcript=transcript)

@app.route('/logout')
def logout():
    """Clear session data"""
    if 'session_id' in session and session['session_id'] in api_key_storage:
        del api_key_storage[session['session_id']]
    session.clear()
    return redirect(url_for('index'))

# Create templates directory
templates_path = 'templates'
os.makedirs(templates_path, exist_ok=True)

# Create template files
index_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Call Audit App</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding-top: 2rem; }
        .container { max-width: 800px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">AI Call Auditing App</h1>
        
        {% if error %}
        <div class="alert alert-danger">{{ error }}</div>
        {% endif %}
        
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Enter Your OpenAI API Key</h5>
                <form method="POST" action="/set_api_key">
                    <div class="mb-3">
                        <label for="api_key" class="form-label">API Key</label>
                        <input type="password" class="form-control" id="api_key" name="api_key" required>
                        <div class="form-text">Your API key is stored only for this session and is never saved to disk.</div>
                    </div>
                    <button type="submit" class="btn btn-primary">Continue</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

audit_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Call Audit - Analyze Transcript</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding-top: 2rem; }
        .container { max-width: 800px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Analyze Call Transcript</h1>
            <a href="/logout" class="btn btn-outline-secondary">Logout</a>
        </div>
        
        {% if error %}
        <div class="alert alert-danger">{{ error }}</div>
        {% endif %}
        
        <div class="card mb-4">
            <div class="card-body">
                <form method="POST" action="/analyze" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label class="form-label">Upload or Enter Transcript</label>
                        <div class="mb-3">
                            <label for="transcript_file" class="form-label">Upload Transcript File</label>
                            <input class="form-control" type="file" id="transcript_file" name="transcript_file">
                        </div>
                        <div class="mb-3">
                            <label for="transcript_text" class="form-label">Or Enter Transcript Text</label>
                            <textarea class="form-control" id="transcript_text" name="transcript_text" rows="10">{{ transcript }}</textarea>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="custom_criteria" class="form-label">Custom Criteria (JSON format, optional)</label>
                        <textarea class="form-control" id="custom_criteria" name="custom_criteria" rows="5">{{ custom_criteria }}</textarea>
                        <div class="form-text">Leave blank to use default criteria</div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">Analyze Transcript</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

results_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Call Audit - Results</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding-top: 2rem; }
        .container { max-width: 900px; }
        .progress { height: 25px; }
        .criteria-card { margin-bottom: 1rem; }
        .transcript-section {
            max-height: 400px;
            overflow-y: auto;
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 0.25rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Call Audit Results</h1>
            <div>
                <a href="/audit" class="btn btn-outline-primary me-2">New Analysis</a>
                <a href="/logout" class="btn btn-outline-secondary">Logout</a>
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-body">
                <div class="row align-items-center mb-4">
                    <div class="col-md-4">
                        <h2 class="mb-0">Overall Score:</h2>
                    </div>
                    <div class="col-md-8">
                        <div class="progress">
                            <div class="progress-bar {{ 'bg-danger' if analysis.overall_score < 4 else 'bg-warning' if analysis.overall_score < 7 else 'bg-success' }}" 
                                 role="progressbar" style="width: {{ analysis.overall_score * 10 }}%">
                                {{ analysis.overall_score }}/10
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-success text-white">
                                <h3 class="h5 mb-0">Strengths</h3>
                            </div>
                            <div class="card-body">
                                <ul>
                                    {% for strength in analysis.strengths %}
                                    <li>{{ strength }}</li>
                                    {% endfor %}
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-warning">
                                <h3 class="h5 mb-0">Areas for Improvement</h3>
                            </div>
                            <div class="card-body">
                                <ul>
                                    {% for area in analysis.areas_for_improvement %}
                                    <li>{{ area }}</li>
                                    {% endfor %}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card mb-4">
                    <div class="card-header">
                        <h3 class="h5 mb-0">Summary</h3>
                    </div>
                    <div class="card-body">
                        {{ analysis.summary }}
                    </div>
                </div>
            </div>
        </div>
        
        <h2>Criteria Scores</h2>
        {% for criterion, details in analysis.criteria_scores.items() %}
        <div class="card criteria-card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h3 class="h5 mb-0">{{ criterion|replace('_', ' ')|title }}</h3>
                <span class="badge {{ 'bg-danger' if details.score < 4 else 'bg-warning' if details.score < 7 else 'bg-success' }}">
                    {{ details.score }}/10
                </span>
            </div>
            <div class="card-body">
                <p>{{ details.assessment }}</p>
                
                {% if details.examples %}
                <h6>Examples:</h6>
                <ul>
                    {% for example in details.examples %}
                    <li><em>"{{ example }}"</em></li>
                    {% endfor %}
                </ul>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        
        <div class="card mt-4">
            <div class="card-header">
                <h3 class="h5 mb-0">Original Transcript</h3>
            </div>
            <div class="card-body">
                <div class="transcript-section">
                    <pre>{{ transcript }}</pre>
                </div>
            </div>
        </div>
        
        <div class="text-center mt-4 mb-5">
            <a href="/audit" class="btn btn-primary">Analyze Another Transcript</a>
        </div>
    </div>
</body>
</html>
"""

# Write template files
with open(os.path.join(templates_path, 'index.html'), 'w') as f:
    f.write(index_html)

with open(os.path.join(templates_path, 'audit.html'), 'w') as f:
    f.write(audit_html)

with open(os.path.join(templates_path, 'results.html'), 'w') as f:
    f.write(results_html)

# Create requirements.txt
requirements_txt = """
flask==2.3.3
openai==1.3.0
gunicorn==21.2.0
"""

with open('requirements.txt', 'w') as f:
    f.write(requirements_txt)

# Create Procfile for Heroku deployment
with open('Procfile', 'w') as f:
    f.write("web: gunicorn app:app")

if __name__ == '__main__':
    app.run(debug=True)
