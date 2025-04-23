from flask import Flask, render_template, request, redirect, flash, jsonify, url_for, send_file, session
import os
from works import create_dash_app
from werkzeug.utils import secure_filename
from data_config import get_dataset_path, fetch_enrollment_records_from_csv, fetch_summary_data_from_csv, get_strand_distribution_by_region
from data_cleaning import clean_data
from datetime import datetime
from report import create_dash_app_report
import pandas as pd
import base64
import uuid
import shutil

# Import functions from your new comparison module
from comparison import find_available_datasets, prepare_comparison_charts_data

app = Flask(__name__)
app.secret_key = 'secret123'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Upload folder config
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
CLEANED_FOLDER = os.path.join(os.path.dirname(__file__), 'cleaned_files')
ACTIVE_DATASET_FOLDER = os.path.join(BASE_DIR, 'active_dataset')
TEMP_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'temp_folder')
# ✅ New: Folder where cleaned datasets will be stored by school year
DATA_MANAGEMENT_FOLDER = os.path.join(os.path.dirname(__file__), 'data_management')

# Ensure all folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)
os.makedirs(DATA_MANAGEMENT_FOLDER, exist_ok=True)
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_data():
    """
    Implement your data saving logic here.
    This function is called when the 'Rerun App' button is clicked.
    You might want to save any uploaded data or modifications to a database or file.
    """
    print("Saving data...")
    # Example: You might save the current dataset path here
    dataset_path = os.path.join(UPLOAD_FOLDER, 'Cleaned_School_DataSet.csv')
    if os.path.exists(dataset_path):
        with open('last_uploaded_dataset.txt', 'w') as f:
            f.write(dataset_path)
        print(f"Dataset path saved to last_uploaded_dataset.txt")
    else:
        print("No dataset path to save.")
    # Add other saving mechanisms as needed

# --- Helper function to find available datasets ---
def find_available_datasets():
    """
    Scans the DATA_MANAGEMENT_FOLDER for school year subdirectories
    containing CSV files.

    Returns:
        dict: A dictionary mapping school years (like 'YYYY-YYYY') to
              the full path of the first CSV file found in that year's folder.
              Sorted by year descending (latest first).
        list: A sorted list of available school year strings.
    """
    datasets = {}
    years = []
    if not os.path.exists(DATA_MANAGEMENT_FOLDER):
        return {}, []

    for year_dir in os.listdir(DATA_MANAGEMENT_FOLDER):
        year_path = os.path.join(DATA_MANAGEMENT_FOLDER, year_dir)
        if os.path.isdir(year_path):
            # Basic check if the directory name looks like a school year
            if "-" in year_dir: # Add more robust check if needed
                for filename in os.listdir(year_path):
                    if filename.lower().endswith(".csv"):
                        full_path = os.path.join(year_path, filename)
                        datasets[year_dir] = full_path
                        years.append(year_dir)
                        break # Found the first CSV, move to next year dir
    
    # Sort years descending (e.g., 2024-2025, 2023-2024)
    years.sort(reverse=True)
    # Create sorted dictionary based on sorted years
    sorted_datasets = {year: datasets[year] for year in years}
    
    return sorted_datasets, years


@app.route("/")
def index():
    return render_template("account.html")

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/otheryear")
def otheryear():
    return render_template("otheryear.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    available_datasets, available_years = find_available_datasets()
    selected_year = session.get('selected_dashboard_year', None)
    selected_file_path = session.get('selected_dashboard_file_path', None)

    if request.method == "POST":
        newly_selected_year = request.form.get("school_year")
        if newly_selected_year in available_datasets:
            selected_year = newly_selected_year
            selected_file_path = available_datasets[selected_year]
            session['selected_dashboard_year'] = selected_year
            session['selected_dashboard_file_path'] = selected_file_path
            print(f"Dashboard: Set selected year to {selected_year}, path: {selected_file_path}") # Debugging
            # Redirect to GET to prevent form resubmission issues
            # and ensure Dash app loads with session updated
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid school year selected.", "warning")
            # Clear potentially invalid session data if selection fails
            session.pop('selected_dashboard_year', None)
            session.pop('selected_dashboard_file_path', None)
            selected_year = None
            selected_file_path = None

    # --- Logic for GET request or if POST failed ---
    if not selected_year and available_years:
        selected_year = available_years[0] # Default to the latest year
        selected_file_path = available_datasets[selected_year]
        session['selected_dashboard_year'] = selected_year
        session['selected_dashboard_file_path'] = selected_file_path
        print(f"Dashboard: Defaulting to latest year {selected_year}, path: {selected_file_path}") # Debugging
    elif selected_year and selected_year not in available_datasets:
        # Handle case where session year is no longer valid (file deleted?)
        flash(f"Previously selected year ({selected_year}) data not found. Please select another.", "warning")
        session.pop('selected_dashboard_year', None)
        session.pop('selected_dashboard_file_path', None)
        selected_year = None
        selected_file_path = None
        # Optionally default again here if desired
        if available_years:
             selected_year = available_years[0] # Default to the latest year
             selected_file_path = available_datasets[selected_year]
             session['selected_dashboard_year'] = selected_year
             session['selected_dashboard_file_path'] = selected_file_path

    # Pass available years and the *currently* selected year to the template
    return render_template("dashboard.html",
                           available_years=available_years,
                           selected_year=selected_year)


@app.route("/comparison")
def comparison():
    return render_template("comparison.html")

@app.route("/report")
def report():
    return render_template("report.html")

@app.route("/help")
def help():
    return render_template("help.html")

@app.route("/logout")
def logout():
    return render_template("logout.html")

import os
from datetime import datetime
from werkzeug.utils import secure_filename

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        # Step 1: Check if file and school_year are present (initial upload)
        if 'file' not in request.files or 'school_year' not in request.form:
            flash('Missing file or school year.')
            return redirect(request.url)

        file = request.files['file']
        school_year = request.form['school_year']

        if file.filename == '':
            flash('No selected file.')
            return redirect(request.url)

        # Step 2: Check if the file is valid
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            renamed_filename = f"{school_year}_Dataset_({filename}).csv"

            school_year_folder = os.path.join(DATA_MANAGEMENT_FOLDER, school_year)
            os.makedirs(school_year_folder, exist_ok=True)
            existing_files = [f for f in os.listdir(school_year_folder) if f.endswith(".csv")]

            if existing_files:
                # Step 3: Trigger the modal
                # Instead of saving to a temp file, we'll read the file data and pass it to the modal
                file_data = file.read()
                file_b64 = base64.b64encode(file_data).decode('utf-8')

                return render_template(
                    "upload.html",
                    show_modal=True,
                    warning_message="This school year already has an active dataset. Uploading a new dataset will replace the current one.",
                    school_year=school_year,
                    filename=filename,
                    file_data=file_b64  # Pass the file data as base64
                )
            else:
                # Step 4: If no existing file, proceed with upload
                temp_file_path = os.path.join(UPLOAD_FOLDER, renamed_filename)
                file.save(temp_file_path)
                try:
                    cleaned_path = clean_data(temp_file_path)
                    final_path = os.path.join(school_year_folder, renamed_filename)
                    os.replace(cleaned_path, final_path)
                    os.remove(temp_file_path)

                    last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    flash(f"Cleaned dataset for {school_year} uploaded successfully!")
                    return render_template("upload.html", last_updated=last_updated)
                except Exception as e:
                    os.remove(temp_file_path)
                    flash(f"Data processing failed: {str(e)}")
                    return redirect(request.url)

        flash("Invalid file type. Please upload a .csv file.")
        return redirect(request.url)

    return render_template("upload.html")

@app.route("/upload_confirm", methods=["POST"])
def upload_confirm():
    school_year = request.form.get('school_year')
    filename = request.form.get('filename')
    file_data_b64 = request.form.get('file_data')

    if not all([school_year, filename, file_data_b64]):
        flash("Missing data for replacement.")
        return redirect(request.url)

    school_year_folder = os.path.join(DATA_MANAGEMENT_FOLDER, school_year)
    renamed_filename = f"{school_year}_Dataset_({filename}).csv"
    final_path = os.path.join(school_year_folder, renamed_filename)

    try:
        # Decode the base64 file data
        file_data = base64.b64decode(file_data_b64)

        # Save the decoded data to a temporary file
        temp_file_path = os.path.join(UPLOAD_FOLDER, renamed_filename)
        with open(temp_file_path, 'wb') as f:
            f.write(file_data)

        existing_files = [f for f in os.listdir(school_year_folder) if f.endswith(".csv")]
        # Step 5: Remove the old file and replace with the new one
        for existing_file in existing_files:
            os.remove(os.path.join(school_year_folder, existing_file))

        cleaned_path = clean_data(temp_file_path)
        os.replace(cleaned_path, final_path)
        os.remove(temp_file_path) # Clean up the temporary file

        last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        flash(f"Existing dataset for {school_year} replaced successfully. Rerun TANAW to activate it!")
        return redirect(url_for('upload')) # Redirect back to the upload page

    except Exception as e:
        flash(f"File replacement failed: {str(e)}")
        return redirect(request.url)

@app.route('/clean', methods=['GET', 'POST'])
def clean():
    if request.method == 'POST':
        uploaded_file = request.files.get('uncleaned_file')
        if uploaded_file and uploaded_file.filename != '':
            filename = secure_filename(uploaded_file.filename)
            raw_path = os.path.join(CLEANED_FOLDER, filename)
            uploaded_file.save(raw_path)

            try:
                cleaned_path = clean_data(raw_path)
                return send_file(cleaned_path, as_attachment=True)

            except Exception as e:
                flash(f"Data cleaning failed: {str(e)}")
                return redirect(request.url)

        flash("No valid file selected for cleaning.")
        return redirect(request.url)

    return render_template('upload.html')

@app.route("/data_management")
def data_management():
    school_years = [f"{year}-{year+1}" for year in range(2016, 2025)]
    datasets = []

    # Path to the currently active dataset
    active_dataset_path = os.path.join(CLEANED_FOLDER, 'Cleaned_School_DataSet.csv')
    active_data = None

    # Read the active dataset if it exists
    if os.path.exists(active_dataset_path):
        with open(active_dataset_path, "r", encoding="utf-8") as f:
            active_data = f.read()

    for year in school_years:
        year_folder = os.path.join(DATA_MANAGEMENT_FOLDER, year)

        # Ensure the school year folder exists
        if not os.path.exists(year_folder):
            os.makedirs(year_folder)

        # List and evaluate datasets within the year folder
        for file in os.listdir(year_folder):
            if file.endswith(".csv"):
                full_path = os.path.join(year_folder, file)

                # Check if this file is the active dataset
                is_active = False
                if active_data is not None:
                    with open(full_path, "r", encoding="utf-8") as f:
                        if f.read() == active_data:
                            is_active = True

                datasets.append({
                    "filename": f"{year}/{file}",
                    "year": year,
                    "active": is_active
                })

    return render_template("data_management.html", datasets=datasets, active_year=None)

@app.route("/preview", methods=["POST"])
def preview():
    filename = request.form.get("filename")
    file_path = os.path.join(DATA_MANAGEMENT_FOLDER, filename)
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        preview_html = df.head(20).to_html(classes="table preview-table")
        return jsonify({"html": preview_html})
    return jsonify({"html": "<p>Error loading preview.</p>"})

@app.route("/replace", methods=["POST"])
def replace():
    original_filename_with_path = request.form.get("filename")
    new_file = request.files.get("new_file")

    # --- Variables for temporary paths ---
    temp_raw_path = None
    cleaned_temp_output_path = None

    # --- Initial checks ---
    if not original_filename_with_path or not new_file:
        flash("Filename or new file missing.", 'error')
        return redirect(url_for("data_management")) # Use the correct endpoint name

    if not allowed_file(new_file.filename):
        flash("Invalid file type for the new file.", 'error')
        return redirect(url_for("data_management"))

    # --- Path definitions ---
    old_file_path = os.path.join(DATA_MANAGEMENT_FOLDER, original_filename_with_path)

    if not os.path.exists(old_file_path):
        # Check if the old file exists before proceeding
        flash(f"Original dataset '{original_filename_with_path}' not found.", 'error')
        return redirect(url_for("data_management"))

    try:
        # --- Determine final target path ---
        relative_dir = os.path.dirname(original_filename_with_path)
        if not relative_dir:
            raise ValueError("Could not determine school year directory from original path.")
        school_year = os.path.basename(relative_dir) # Extract school year if needed for naming

        uploaded_filename = new_file.filename # Keep original uploaded filename for base
        new_base_name, file_ext = os.path.splitext(uploaded_filename) # Get base name

        # Define the final filename for the *cleaned* data (adjust naming as needed)
        # Using original base name + _cleaned suffix
        new_target_filename_only = f"{school_year}_Dataset_({new_base_name})_cleaned{file_ext}"
        new_target_path = os.path.join(DATA_MANAGEMENT_FOLDER, relative_dir, new_target_filename_only)

        # --- Save uploaded file temporarily ---
        os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
        # Create a unique temp filename to avoid conflicts
        temp_filename = f"temp_replace_{uuid.uuid4()}_{uploaded_filename}"
        temp_raw_path = os.path.join(TEMP_UPLOAD_FOLDER, temp_filename)
        new_file.save(temp_raw_path)
        print(f"Saved uploaded file temporarily to: {temp_raw_path}")

        # --- Clean the temporary file using the ORIGINAL clean_data ---

        print(f"Attempting to clean '{temp_raw_path}' using original clean_data...")
        try:
            # Call your unmodified clean_data function
            cleaned_temp_output_path = clean_data(temp_raw_path)

            # Basic check: Ensure clean_data returned a string path
            if not cleaned_temp_output_path or not isinstance(cleaned_temp_output_path, str):
                 print("clean_data did not return a valid path string.")
                 # Treat as failure, raise an error to be caught by outer except block
                 raise ValueError("Data cleaning process failed to produce an output file path.")
            if not os.path.exists(cleaned_temp_output_path):
                 print(f"clean_data returned path '{cleaned_temp_output_path}' but file does not exist.")
                 raise ValueError("Data cleaning process failed, output file not found.")

            print(f"clean_data successful, returned path: {cleaned_temp_output_path}")

        except (ValueError, TypeError, OSError, Exception) as clean_error:
            # Catch potential errors specifically from clean_data
            print(f"Data cleaning function failed with error: {clean_error}")
            flash(f"Data cleaning failed for '{uploaded_filename}': {str(clean_error)}. The original dataset was not replaced.", 'error')
            raise clean_error

        print(f"Moving cleaned file from '{cleaned_temp_output_path}' to '{new_target_path}'")
        shutil.move(cleaned_temp_output_path, new_target_path)

        # --- Success: File moved, now remove the original old file ---
        print(f"Cleaned file moved successfully. Removing old file: {old_file_path}")
        try:
            os.remove(old_file_path)
            print(f"Removed old file: {old_file_path}")
        except OSError as e:
            # Log error but proceed; maybe flash a warning
            print(f"Warning: Could not remove old file '{old_file_path}'. Error: {e}")
            flash(f"Warning: Replaced data, but could not remove old file '{os.path.basename(original_filename_with_path)}'.", 'warning')


        saved_relative_path = os.path.join(relative_dir, new_target_filename_only)
        #flash(f"Dataset '{os.path.basename(original_filename_with_path)}' replaced and cleaned successfully (saved as '{saved_relative_path}').", 'success')

    # --- Outer error handling ---
    except (ValueError, TypeError, OSError) as e: # Catch errors from file ops, path processing, or re-raised clean_error
        if "Data cleaning failed" not in str(e): # Simple check
             flash(f"Error during replacement process: {str(e)}", 'error')
        # Ensure the old file is NOT removed if we land here due to an error BEFORE os.remove(old_file_path)
    except Exception as e:
        flash(f"An unexpected error occurred during replacement: {str(e)}", 'error')
        print(f"Unexpected error in /replace: {e}") # Log details for debugging
    finally:
        # --- Clean up temporary files ---
        # Always remove the initial raw temporary file if it exists
        if temp_raw_path and os.path.exists(temp_raw_path):
            try:
                os.remove(temp_raw_path)
                print(f"Removed temporary raw input file: {temp_raw_path}")
            except OSError as e:
                print(f"Error removing temporary raw input file '{temp_raw_path}': {e}")

        # Attempt to clean up the temporary *output* file from clean_data IF it exists
        # This handles cases where clean_data succeeded but the move failed, or if clean_data errored *after* creating the file.
        if cleaned_temp_output_path and os.path.exists(cleaned_temp_output_path):
            # Check if it still exists (it shouldn't if the move was successful)
             print(f"Cleaning up temporary output file: {cleaned_temp_output_path}")
             try:
                 # Optionally remove the 'cleaned_files' directory if it's empty and inside TEMP_UPLOAD_FOLDER
                 cleaned_dir = os.path.dirname(cleaned_temp_output_path)
                 os.remove(cleaned_temp_output_path) # Remove the file first
                 if os.path.basename(cleaned_dir) == 'cleaned_files' and \
                    os.path.normpath(os.path.dirname(cleaned_dir)) == os.path.normpath(TEMP_UPLOAD_FOLDER) and \
                    not os.listdir(cleaned_dir): # Check if empty after removing file
                      os.rmdir(cleaned_dir)
                      print(f"Removed empty temporary cleaned_files directory: {cleaned_dir}")
             except OSError as e:
                 print(f"Error removing temporary output file or dir '{cleaned_temp_output_path}': {e}")


    return redirect(url_for("data_management")) 

@app.route("/download", methods=["POST"])
def download():
    filename = request.form.get("filename")
    file_path = os.path.join(DATA_MANAGEMENT_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    flash("File not found.")
    return redirect(url_for("data_management"))

@app.route("/delete", methods=["POST"])
def delete():
    filename = request.form.get("filename")
    file_path = os.path.join(DATA_MANAGEMENT_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash("File deleted successfully.")
    else:
        flash("File not found.")
    return redirect(url_for("data_management"))

# sample
@app.route("/download-template")
def download_template():
    return send_file("static/sample_template.csv", as_attachment=True)

@app.route('/api/enrollment_data')
@app.route('/api/enrollment_data')
def get_enrollment_data():
    # OPTION 1: Get path from session (if API is called AFTER year selection)
    file_path = session.get('selected_dashboard_file_path')

    # OPTION 2: Pass year as query parameter (e.g., /api/enrollment_data?year=2023-2024)
    # selected_year = request.args.get('year')
    # available_datasets, _ = find_available_datasets()
    # file_path = available_datasets.get(selected_year)

    if not file_path or not os.path.exists(file_path):
        # Fallback or error handling: Use default, latest, or return error
        available_datasets, years = find_available_datasets()
        if years:
             file_path = available_datasets[years[0]] # Fallback to latest
             print(f"API Warning: No specific path found, falling back to latest: {file_path}")
        else:
             # Or maybe use the original default static path if it exists?
             # file_path = get_dataset_path()
             # if not os.path.exists(file_path):
             return jsonify({"error": "No dataset selected or available."}), 404

    print(f"API: Using data path: {file_path}") # Debugging
    try:
        # Use the dynamically determined file_path
        # Note: fetch_enrollment_records_from_csv seems unused here based on previous code
        summary_data = fetch_summary_data_from_csv(file_path)
        strand_data = get_strand_distribution_by_region(file_path)

        # Check if data loading was successful (functions might return {} on error)
        if not summary_data:
             return jsonify({"error": f"Failed to load summary data from {file_path}"}), 500

        summary_data['strandRegionMatrix'] = strand_data
        return jsonify(summary_data)
    except Exception as e:
        print(f"API Error: Failed to process data for {file_path}: {e}")
        return jsonify({"error": f"Internal server error processing data: {str(e)}"}), 500


@app.route('/rerun_app', methods=['POST'])
def rerun_app():
    print("Rerunning the Flask application (simulated).")
    save_data()

    try:
        with open(__file__, 'r') as f:
            content = f.readlines()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content.append(f"# Triggering auto-reload at {timestamp}\n")

        with open(__file__, 'w') as f:
            f.writelines(content) 

        flash("TANAW is now Reloaded!", 'success')

    except Exception as e:
        flash(f"Error triggering auto-reload: {str(e)}", "error")

    return redirect(url_for('home'))

# --- Updated Comparison Route ---
@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """
    Handles the comparison page, allowing users to select and compare data
    from two different school years.
    """
    # Call find_available_datasets from the comparison module
    available_datasets, available_years = find_available_datasets()

    selected_year_1 = session.get('selected_comparison_year_1', None)
    selected_year_2 = session.get('selected_comparison_year_2', None)

    comparison_data = None # This will hold the data structure for your visualizations
    selected_file_path_1 = None
    selected_file_path_2 = None

    print(f"Compare (Initial/GET): Session years - Year 1: {selected_year_1}, Year 2: {selected_year_2}") # Debugging


    if request.method == 'POST':
        newly_selected_year_1 = request.form.get('school_year_1')
        newly_selected_year_2 = request.form.get('school_year_2')

        print(f"Compare (POST): Received years - Year 1: {newly_selected_year_1}, Year 2: {newly_selected_year_2}") # Debugging

        # --- Validation ---
        validation_error = None
        if not newly_selected_year_1 or not newly_selected_year_2:
            validation_error = "Please select both school years for comparison."
        elif newly_selected_year_1 not in available_datasets or newly_selected_year_2 not in available_datasets:
             validation_error = "One or both selected school years are invalid."
        elif newly_selected_year_1 == newly_selected_year_2:
            validation_error = "Please select two *different* years for comparison."

        if validation_error:
            flash(validation_error, "warning")
            print(f"Validation failed: {validation_error}") # Debugging
            # Keep existing session selections if they exist
            # Note: The template will render with the years from the POST request
            # even if validation failed, but the flash message will explain why
            # no comparison data is shown.
            selected_year_1 = newly_selected_year_1 # Keep the years the user tried to select
            selected_year_2 = newly_selected_year_2
        else:
            # --- Validation Passed ---
            print("Validation successful. Updating session and redirecting.") # Debugging
            selected_year_1 = newly_selected_year_1
            selected_year_2 = newly_selected_year_2

            # Store the validated selected years in the session
            session['selected_comparison_year_1'] = selected_year_1
            session['selected_comparison_year_2'] = selected_year_2

            # Redirect to the GET route to prevent form resubmission on refresh
            return redirect(url_for('compare'))

    # --- Logic for GET request or after POST redirect/failure ---

    # If we have selected years in the session (either from initial GET or after a successful POST redirect),
    # and they are valid, load and process the data for comparison.
    if selected_year_1 and selected_year_2 \
       and selected_year_1 in available_datasets and selected_year_2 in available_datasets \
       and selected_year_1 != selected_year_2: # Ensure they are different, even if session somehow stored same

        print(f"Compare (GET/Post-Redirect): Loading data for {selected_year_1} vs {selected_year_2} from session.") # Debugging
        selected_file_path_1 = available_datasets[selected_year_1]
        selected_file_path_2 = available_datasets[selected_year_2]

        # --- Call the data processing function from the comparison module ---
        comparison_data = prepare_comparison_charts_data(
            selected_file_path_1,
            selected_file_path_2,
            selected_year_1, # Pass years as labels for charts
            selected_year_2
        )

        if comparison_data is None:
             flash("Failed to load or process data for comparison.", "danger")
             print("Error: prepare_comparison_charts_data returned None.") # Debugging
             # Optionally clear session if data loading failed
             session.pop('selected_comparison_year_1', None)
             session.pop('selected_comparison_year_2', None)
             selected_year_1 = None
             selected_year_2 = None


    elif (selected_year_1 or selected_year_2) and \
         (selected_year_1 not in available_datasets or selected_year_2 not in available_datasets or selected_year_1 == selected_year_2):
         # Handle case where session years are no longer valid or are the same
         # This might happen if available_datasets changed since the session was set
         flash("Data for previously selected comparison years not found or years are the same. Please select again.", "warning")
         print("Session years invalid or same. Clearing session.") # Debugging
         session.pop('selected_comparison_year_1', None)
         session.pop('selected_comparison_year_2', None)
         selected_year_1 = None
         selected_year_2 = None
         comparison_data = None # Ensure no old data is shown


    # Render the comparison template
    return render_template('comparison_page.html',
                           available_years=available_years,
                           selected_year_1=selected_year_1,
                           selected_year_2=selected_year_2,
                           comparison_data=comparison_data # Pass the data structure for template to use
                          )

# Mount Dash app
dash_app_works = create_dash_app(app)
dash_app_report = create_dash_app_report(app)

if __name__ == "__main__":
    app.run(debug=True)# Triggering auto-reload at 2025-04-22 02:13:27
# Triggering auto-reload at 2025-04-22 03:01:20
# Triggering auto-reload at 2025-04-22 03:36:24
# Triggering auto-reload at 2025-04-23 01:42:02
# Triggering auto-reload at 2025-04-23 01:46:16
# Triggering auto-reload at 2025-04-23 02:24:32
# Triggering auto-reload at 2025-04-23 16:38:01
