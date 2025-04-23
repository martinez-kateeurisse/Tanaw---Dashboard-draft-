# comparison.py

import os
import pandas as pd
import re

# Assuming your datasets are in a 'static' folder relative to where app.py and comparison.py are
DATA_DIR = os.path.join(os.path.dirname(__file__), 'static')

def find_available_datasets():
    """
    Finds available datasets (e.g., CSV files in 'static') and extracts school years.
    Assumes filenames are like 'YYYY-YYYY_*.csv'.
    Returns a dictionary mapping year to file path and a sorted list of years (latest first).
    """
    print("Finding available datasets...") # Debugging
    available_datasets = {}
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            # Use regex to find files matching the 'YYYY-YYYY' pattern
            match = re.match(r'(\d{4}-\d{4})_.*\.csv$', filename)
            if match:
                year = match.group(1)
                available_datasets[year] = os.path.join(DATA_DIR, filename)

    available_years = sorted(available_datasets.keys(), reverse=True) # Sort years, latest first
    print(f"Found years: {available_years}") # Debugging
    return available_datasets, available_years

def prepare_comparison_charts_data(file_path_1, file_path_2, year1_label, year2_label):
    """
    Loads data from two CSV files, processes it for comparison charts,
    and returns a dictionary structured for frontend visualization libraries (like Chart.js).
    Returns None if file processing fails.
    """
    comparison_data = {
        'year1_label': year1_label,
        'year2_label': year2_label,
        'total_enrollment': {},
        'enrollment_by_year_level': {
            'labels': [],
            'datasets': [
                {'label': year1_label, 'data': [], 'backgroundColor': 'rgba(54, 162, 235, 0.6)'}, # Example colors
                {'label': year2_label, 'data': [], 'backgroundColor': 'rgba(255, 99, 132, 0.6)'}
            ]
        },
        'enrollment_by_region': {
            'labels': [],
            'datasets': [
                 {'label': year1_label, 'data': [], 'backgroundColor': 'rgba(54, 162, 235, 0.6)'},
                 {'label': year2_label, 'data': [], 'backgroundColor': 'rgba(255, 99, 132, 0.6)'}
            ]
        }
        # Add more data structures for other comparison charts here as needed
    }

    # Define columns for year levels and regions (based on your dashboard logic)
    # Ensure these match the columns in your CSV files
    grade_columns = {
        'Kindergarten': ['K Male', 'K Female'],
        'Grade 1': ['G1 Male', 'G1 Female'],
        'Grade 2': ['G2 Male', 'G2 Female'],
        'Grade 3': ['G3 Male', 'G3 Female'],
        'Grade 4': ['G4 Male', 'G4 Female'],
        'Grade 5': ['G5 Male', 'G5 Female'],
        'Grade 6': ['G6 Male', 'G6 Female'],
        'Grade 7': ['G7 Male', 'G7 Female'],
        'Grade 8': ['G8 Male', 'G8 Female'],
        'Grade 9': ['G9 Male', 'G9 Female'],
        'Grade 10': ['G10 Male', 'G10 Female'],
        'Grade 11': [
            'G11 ACAD - ABM Male', 'G11 ACAD - ABM Female',
            'G11 ACAD - HUMSS Male', 'G11 ACAD - HUMSS Female',
            'G11 ACAD STEM Male', 'G11 ACAD STEM Female',
            'G11 ACAD GAS Male', 'G11 ACAD GAS Female',
            'G11 ACAD PBM Male', 'G11 ACAD PBM Female',
            'G11 TVL Male', 'G11 TVL Female',
            'G11 SPORTS Male', 'G11 SPORTS Female',
            'G11 ARTS Male', 'G11 ARTS Female'
        ],
        'Grade 12': [
            'G12 ACAD - ABM Male', 'G12 ACAD - ABM Female',
            'G12 ACAD - HUMSS Male', 'G12 ACAD - HUMSS Female',
            'G12 ACAD STEM Male', 'G12 ACAD STEM Female',
            'G12 ACAD GAS Male', 'G12 ACAD GAS Female',
            'G12 ACAD PBM Male', 'G12 ACAD PBM Female',
            'G12 TVL Male', 'G12 TVL Female',
            'G12 SPORTS Male', 'G12 SPORTS Female',
            'G12 ARTS Male', 'G12 ARTS Female'
        ]
    }

    # Function to process a single file
    def process_single_file(file_path):
        """Loads and processes data from a single CSV file."""
        try:
            df = pd.read_csv(file_path)
            # Normalize column names
            df.columns = df.columns.str.strip().str.replace('–', '-', regex=False).str.replace('—', '-', regex=False)

            # Calculate Total Enrollment per row
            male_cols = [col for col in df.columns if re.search(r'\bmale\b', col, re.IGNORECASE)]
            female_cols = [col for col in df.columns if re.search(r'\bfemale\b', col, re.IGNORECASE)]
            all_gender_cols = male_cols + female_cols

            # Ensure all gender columns exist before trying to convert/sum
            existing_gender_cols = [col for col in all_gender_cols if col in df.columns]

            if not existing_gender_cols:
                 print(f"Warning: No male or female enrollment columns found in {file_path}")
                 df['TotalEnrollment'] = 0 # Set total enrollment to 0 if no data cols

            else:
                for col in existing_gender_cols:
                     df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0) # Convert to numeric, fill NaNs with 0

                df['TotalEnrollment'] = df[existing_gender_cols].sum(axis=1)


            # Calculate Total Enrollment for the year
            total_enrollment = int(df['TotalEnrollment'].sum())

            # Calculate Enrollment by Year Level
            enrollment_by_year_level = {}
            for grade, columns in grade_columns.items():
                valid_cols = [col for col in columns if col in df.columns]
                enrollment_by_year_level[grade] = int(df[valid_cols].sum().sum()) if valid_cols else 0

            # Calculate Enrollment by Region
            region_col = next((col for col in df.columns if col.strip().lower() == 'region'), None)
            enrollment_by_region = {}
            if region_col and region_col in df.columns:
                 # Ensure region column is string type to avoid issues with grouping
                 df[region_col] = df[region_col].astype(str)
                 # Group by region and sum total enrollment
                 enrollment_by_region = (
                     df.groupby(region_col)['TotalEnrollment'].sum().astype(int).to_dict()
                 )
            else:
                 print(f"Warning: Region column not found in {file_path}")


            return {
                'total_enrollment': total_enrollment,
                'enrollment_by_year_level': enrollment_by_year_level,
                'enrollment_by_region': enrollment_by_region
            }

        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return None
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            return None

    # Process data for both years
    data1 = process_single_file(file_path_1)
    data2 = process_single_file(file_path_2)

    if data1 is None or data2 is None:
        # Return None if either file failed to process
        return None

    # Populate comparison_data structure

    # Total Enrollment Comparison
    comparison_data['total_enrollment'] = {
        'labels': [year1_label, year2_label],
        'datasets': [{
            'label': 'Total Enrollment',
            'data': [data1['total_enrollment'], data2['total_enrollment']],
            'backgroundColor': ['rgba(54, 162, 235, 0.6)', 'rgba(255, 99, 132, 0.6)'],
        }]
    }

    # Enrollment by Year Level Comparison
    # Get all unique year levels from both datasets
    # Use the order defined in grade_columns for consistent chart labels
    all_year_levels_ordered = [level for level in grade_columns.keys() if level in data1['enrollment_by_year_level'] or level in data2['enrollment_by_year_level']]

    comparison_data['enrollment_by_year_level']['labels'] = all_year_levels_ordered
    comparison_data['enrollment_by_year_level']['datasets'][0]['data'] = [data1['enrollment_by_year_level'].get(level, 0) for level in all_year_levels_ordered]
    comparison_data['enrollment_by_year_level']['datasets'][1]['data'] = [data2['enrollment_by_year_level'].get(level, 0) for level in all_year_levels_ordered]


    # Enrollment by Region Comparison
    # Get all unique regions from both datasets and sort alphabetically
    all_regions = sorted(list(set(data1['enrollment_by_region'].keys()) | set(data2['enrollment_by_region'].keys())))

    comparison_data['enrollment_by_region']['labels'] = all_regions
    comparison_data['enrollment_by_region']['datasets'][0]['data'] = [data1['enrollment_by_region'].get(region, 0) for region in all_regions]
    comparison_data['enrollment_by_region']['datasets'][1]['data'] = [data2['enrollment_by_region'].get(region, 0) for region in all_regions]


    return comparison_data

# You can add other comparison-specific data processing functions here later
# def prepare_gender_ratio_comparison(...):
#    pass
