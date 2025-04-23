import os
import pandas as pd
from datetime import datetime
import re
from difflib import get_close_matches
import numpy as np # Import numpy

standard_columns = [
    # ... (standard_columns) ...
    "K Male", "K Female", "G1 Male", "G1 Female", "G2 Male", "G2 Female", "G3 Male", "G3 Female",
    "G4 Male", "G4 Female", "G5 Male", "G5 Female", "G6 Male", "G6 Female",
    "Elem NG Male", "Elem NG Female", "G7 Male", "G7 Female", "G8 Male", "G8 Female",
    "G9 Male", "G9 Female", "G10 Male", "G10 Female", "JHS NG Male", "JHS NG Female",
    "G11 ACAD - ABM Male", "G11 ACAD - ABM Female", "G11 ACAD - HUMSS Male", "G11 ACAD - HUMSS Female",
    "G11 ACAD STEM Male", "G11 ACAD STEM Female", "G11 ACAD GAS Male", "G11 ACAD GAS Female",
    "G11 ACAD PBM Male", "G11 ACAD PBM Female", "G11 TVL Male", "G11 TVL Female",
    "G11 SPORTS Male", "G11 SPORTS Female", "G11 ARTS Male", "G11 ARTS Female",
    "G12 ACAD - ABM Male", "G12 ACAD - ABM Female", "G12 ACAD - HUMSS Male", "G12 ACAD - HUMSS Female",
    "G12 ACAD STEM Male", "G12 ACAD STEM Female", "G12 ACAD GAS Male", "G12 ACAD GAS Female",
    "G12 ACAD PBM Male", "G12 ACAD PBM Female", "G12 TVL Male", "G12 TVL Female",
    "G12 SPORTS Male", "G12 SPORTS Female", "G12 ARTS Male", "G12 ARTS Female"
]

region_mapping = {
    # ... (region_mapping) ...
     'barmm': 'BARMM', 'bangsamoro': 'BARMM', 'car': 'CAR', 'cordillera': 'CAR', 'caraga': 'CARAGA',
     'mimaropa': 'MIMAROPA', 'ncr': 'NCR', 'national capital region': 'NCR', 'pso': 'PSO',
     'region i': 'Region I', 'region 1': 'Region I', 'region ii': 'Region II', 'region 2': 'Region II',
     'region iii': 'Region III', 'region 3': 'Region III', 'region iv-a': 'Region IV-A',
     'region 4a': 'Region IV-A', 'region iva': 'Region IV-A', 'region v': 'Region V', 'region 5': 'Region V',
     'region vi': 'Region VI', 'region 6': 'Region VI', 'region vii': 'Region VII', 'region 7': 'Region VII',
     'region viii': 'Region VIII', 'region 8': 'Region VIII', 'region ix': 'Region IX', 'region 9': 'Region IX',
     'region x': 'Region X', 'region 10': 'Region X', 'region xi': 'Region XI', 'region 11': 'Region XI',
     'region xii': 'Region XII', 'region 12': 'Region XII',
}

def standardize_region_values(val):
     if isinstance(val, str):
         val_lower = val.strip().lower()
         # First, check direct mapping
         if val_lower in region_mapping:
             return region_mapping[val_lower]
         # Try regex extraction if direct map fails
         match = re.search(r'\b(region\s?[ixv0-9\-a]+|ncr|caraga|car|barmm|pso)\b', val_lower)
         if match:
             code = match.group(1).replace(" ", "").replace("-", "").lower()
             # Normalize known variations within mapping keys before check
             norm_code = code
             if norm_code.startswith('region'):
                 norm_code = norm_code.replace('region', '').strip()
                 # Try to map Roman numerals if needed, simple cases here
                 roman_map = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii':'7', 'viii':'8', 'ix':'9', 'x':'10', 'xi': '11', 'xii': '12'}
                 if norm_code in roman_map:
                     norm_code = roman_map[norm_code]
                 # Reconstruct key format
                 norm_code = f"region {norm_code}" # Aim for 'region #' format for lookup

             # Check normalized code against normalized keys
             for key, standard in region_mapping.items():
                 norm_key = key.replace("-","") # Normalize key for comparison
                 if norm_key == norm_code.replace("-",""): # Compare normalized forms
                    return standard
         return val.strip() # Return original stripped if no match
     return val


def preprocess_column(col):
    col = str(col).upper().strip()

    if col == 'NAN' or col is None:
        return None

    # --- Early Cleanups ---
    # Remove parentheses around content first, also handles nested like (elem Ng)
    col = re.sub(r'\(\s*(.*?)\s*\)', r'\1', col) # Remove (), trim inside space
    # Remove extra spaces generated or pre-existing
    col = re.sub(r'\s{2,}', ' ', col).strip()

    # --- Specific Standardizations ---

    # --- Fix Specific Malformed NG Inputs & Spacing ---
    # Ensure space between known NG-related terms
    col = re.sub(r'\b(NG)\s*(ELEM)\b', r'\1 \2', col, flags=re.IGNORECASE) # NG ELEM -> NG ELEM
    col = re.sub(r'\b(NG)\s*(JHS)\b', r'\1 \2', col, flags=re.IGNORECASE)  # NG JHS -> NG JHS
    col = re.sub(r'\b(NG)\s*(MALE)\b', r'\1 \2', col, flags=re.IGNORECASE) # NG MALE -> NG MALE
    col = re.sub(r'\b(NG)\s*(FEMALE)\b', r'\1 \2', col, flags=re.IGNORECASE)# NG FEMALE -> NG FEMALE
    col = re.sub(r'\b(ELEM)\s*(NG)\b', r'\1 \2', col, flags=re.IGNORECASE) # ELEM NG -> ELEM NG (Standard)
    col = re.sub(r'\b(JHS)\s*(NG)\b', r'\1 \2', col, flags=re.IGNORECASE)  # JHS NG -> JHS NG (Standard)

    # Fix common run-together words explicitly
    if 'NGELEM' in col: col = col.replace('NGELEM', 'NG ELEM')
    if 'NGJHS' in col: col = col.replace('NGJHS', 'NG JHS')
    if 'NGMALE' in col: col = col.replace('NGMALE', 'NG MALE')
    if 'NGFEMALE' in col: col = col.replace('NGFEMALE', 'NG FEMALE')

    # Normalize spaces again after potential insertions
    col = re.sub(r'\s{2,}', ' ', col).strip()

    # --- Standardize NG Format and Order ---
    # Ensure correct order: Level NG (run AFTER fixing spacing above)
    col = re.sub(r'\bNG\s+ELEM\b', 'ELEM NG', col, flags=re.IGNORECASE) # NG ELEM -> ELEM NG
    col = re.sub(r'\bNG\s+JHS\b', 'JHS NG', col, flags=re.IGNORECASE)   # NG JHS -> JHS NG

    # Ensure base ELEM/JHS names are standardized BEFORE adding NG
    col = re.sub(r'\b(ES|ELEM|ELEMENTARY)\b', 'ELEM', col, flags=re.IGNORECASE) # Standardize ELEM name
    col = re.sub(r'\b(JHS|JUNIOR\s+HIGH\s*SCHOOL)\b', 'JHS', col, flags=re.IGNORECASE) # Standardize JHS name

    col = re.sub(r'\bELEM\b(?!\s+NG)', 'ELEM NG', col, flags=re.IGNORECASE) # Add NG to ELEM if missing
    col = re.sub(r'\bJHS\b(?!\s+NG)', 'JHS NG', col, flags=re.IGNORECASE)   # Add NG to JHS if missing

    # --- Handle NON-GRADED Prefix based on context ---
    non_graded_pattern = r'\bNON\s*[-–]?\s*GRADED?\b'
    if re.search(r'\b(ELEM|JHS)\b', col, flags=re.IGNORECASE):
        col = re.sub(non_graded_pattern, '', col, flags=re.IGNORECASE)
    else:
        
        col = re.sub(non_graded_pattern, 'NG', col, flags=re.IGNORECASE)
    # Clean up extra spaces potentially left by removal/replacement
    col = re.sub(r'\s{2,}', ' ', col).strip()

    # Map Maritime to PBM (assuming this is correct based on standard_columns)
    col = re.sub(r'\bMARITIME\b', 'PBM', col, flags=re.IGNORECASE)

    # Standardize Grade Levels and Kindergarten AFTER specific NG/Maritime handling
    col = re.sub(r'KINDERGARTEN', 'K', col, flags=re.IGNORECASE)
    col = re.sub(r'\bGRADE\s*(\d{1,2})\b', r'G\1', col, flags=re.IGNORECASE) # G1, G10 etc.

    # --- SHS Specific Standardization ---

    # 1. Standardize Track Names
    col = re.sub(r'\bARTS\s*([&AND]+\s*)?DESIGN\b', 'ARTS', col, flags=re.IGNORECASE)
    col = re.sub(r'\bACADEMIC\s*(TRACK)?\b', 'ACAD', col, flags=re.IGNORECASE)
    col = re.sub(r'\bTECHNICAL\s*[-–]?\s*VOCATIONAL\s*[-–]?\s*(LIVELIHOOD|TVL)\b', 'TVL', col, flags=re.IGNORECASE)

    # 2. Combine Grade + Track/Strand using replacement functions

    def replace_acad_hyphen(match):
        grade = match.group(1)
        strand = match.group(3)
        return f"{grade} ACAD - {strand}"

    def replace_acad_no_hyphen(match):
        grade = match.group(1)
        strand = match.group(3)
        return f"{grade} ACAD {strand}"

    # Apply for ABM/HUMSS
    col = re.sub(
        r'\b(G11|G12)\b'           # Group 1: Grade
        r'(?:\s*[-–]?\s*)'       # Optional separator
        r'(ACAD\s*[-–]?\s*)?'     # Group 2: Optional ACAD part
        r'\b(ABM|HUMSS)\b',        # Group 3: Strand
        replace_acad_hyphen, col, flags=re.IGNORECASE
    )

    # Apply for STEM/GAS/PBM (now includes PBM via Maritime mapping)
    col = re.sub(
        r'\b(G11|G12)\b'           # Group 1: Grade
        r'(?:\s*[-–]?\s*)'       # Optional separator
        r'(ACAD\s*[-–]?\s*)?'     # Group 2: Optional ACAD part
        r'\b(STEM|GAS|PBM)\b',     # Group 3: Strand
        replace_acad_no_hyphen, col, flags=re.IGNORECASE
    )

    # Standardize other tracks (TVL/SPORTS/ARTS)
    col = re.sub(r'\b(G11|G12)\b\s*[-–]?\s*\b(TVL|SPORTS|ARTS)\b', r'\1 \2', col, flags=re.IGNORECASE)

    # --- Final Cleanup ---
    col = re.sub(r'\s{2,}', ' ', col).strip()

    # Add specific check for NG ordering just in case
    col = re.sub(r'\bNG\s+ELEM\b', 'ELEM NG', col, flags=re.IGNORECASE)
    col = re.sub(r'\bNG\s+JHS\b', 'JHS NG', col, flags=re.IGNORECASE)


    return col

def standardize_column_name(col):
    processed_col = preprocess_column(col)
    if processed_col is None: 
        return None 

    # Capitalization logic (similar to before)
    parts = processed_col.split()
    capitalized_parts = []
    for part in parts:
        part_upper = part.upper()
        if part_upper in ['TVL', 'STEM', 'ABM', 'HUMSS', 'GAS', 'PBM', 'NG', 'JHS', 'ACAD']:
            capitalized_parts.append(part_upper)
        elif part_upper == 'K':
             capitalized_parts.append('K') # Keep K uppercase
        elif part_upper.startswith('G') and part_upper[1:].isdigit():
             capitalized_parts.append(part_upper) # Keep G1, G2 etc uppercase
        else:
            capitalized_parts.append(part.capitalize())
    final_col = ' '.join(capitalized_parts)

    # Final check against standard columns using closeness
    # Ensure standard_columns are defined in the scope or passed as an argument
    match = get_close_matches(final_col, standard_columns, n=1, cutoff=0.85) 
    return match[0] if match else final_col # Return best match or the processed name if no close match


def check_if_already_cleaned(df, standard_enrollment_cols):
    """Checks if the DataFrame appears to be already cleaned."""
    if df.empty:
        return False
    
    # Check 1: Column names match the standard?
    current_cols = df.columns.tolist()
    expected_cols_subset = ['Region'] + standard_enrollment_cols
    # Allow for other non-enrollment cols potentially present in cleaned school files
    if not all(col in current_cols for col in ['Region']): # Must have Region
         return False
    
    present_standard_cols = [col for col in expected_cols_subset if col in current_cols]
    if len(present_standard_cols) < 0.8 * len(expected_cols_subset): # Heuristic: at least 80% match?
        # print("DEBUG: Column names don't sufficiently match standard.")
        return False

    # Check 2: Data types are mostly numeric for enrollment columns?
    numeric_cols_count = 0
    enrollment_cols_in_df = [col for col in standard_enrollment_cols if col in df.columns]
    
    if not enrollment_cols_in_df: # No standard enrollment columns found
        # print("DEBUG: No standard enrollment columns found.")
        return False

    # Check a sample of rows for numeric types
    sample_rows = min(len(df), 5) # Check up to 5 rows
    if sample_rows == 0:
         return False # Empty dataframe after header

    for col in enrollment_cols_in_df:
        try:
            # Attempt conversion on a sample; check if mostly numeric/NaN
            pd.to_numeric(df[col].iloc[:sample_rows], errors='raise')
            numeric_cols_count += 1
        except (ValueError, TypeError):
            # Check if conversion fails due to non-numeric strings, ignore if already numeric/NaN
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            is_mostly_nan_or_zero = df[col].iloc[:sample_rows].fillna(0).isin([0, np.nan]).mean() > 0.8
            if is_numeric or is_mostly_nan_or_zero:
                 numeric_cols_count += 1 # Count if already numeric or mostly zero/NaN
            # else:
                 # print(f"DEBUG: Column '{col}' sample not easily convertible to numeric.")
                 # pass # Fails numeric check

    # Heuristic: If a high percentage of expected enrollment columns are numeric-like
    if numeric_cols_count >= 0.8 * len(enrollment_cols_in_df):
        # print("DEBUG: File appears already cleaned based on columns and data types.")
        return True
    else:
        # print(f"DEBUG: Numeric check failed. Count: {numeric_cols_count} / {len(enrollment_cols_in_df)}")
        return False


def clean_data(file_path):
    cleaned_files_directory = os.path.join(os.path.dirname(file_path), 'cleaned_files') # More robust path finding
    os.makedirs(cleaned_files_directory, exist_ok=True)

    # --- Try reading with header=0 first to check if it's already clean ---
    try:
        df_check = pd.read_csv(file_path, header=0, low_memory=False)
         # Define the expected enrollment columns for the check
        is_cleaned = check_if_already_cleaned(df_check, standard_columns)
    except Exception as e:
        # print(f"DEBUG: Initial read with header=0 failed or check failed: {e}")
        is_cleaned = False
        df_check = None # Ensure df_check is None if read fails

    if is_cleaned and df_check is not None:
        print("--- File appears already cleaned. Skipping intensive cleaning. ---")
        # Optional: Perform minimal validation if needed (e.g., ensure region values are standard)
        if 'Region' in df_check.columns:
             df_check['Region'] = df_check['Region'].apply(standardize_region_values)
        df_cleaned = df_check # Use the successfully read and checked DataFrame
        # Proceed directly to saving
    else:
        print("--- File needs cleaning or is not standard format. Performing full cleaning. ---")
        # --- Proceed with the original logic for raw files ---
        df = pd.read_csv(file_path, header=None, low_memory=False) # Read without header
        df = df.applymap(lambda x: standardize_region_values(x) if isinstance(x, str) else x) # Apply region standardization cell-wise

        # Detect header row (keep your existing logic)
        potential_headers = ['Region', 'Kindergarten', 'Grade 1', 'Grade 2', 'G1', 'G2']
        header_row_index = None
        for idx, row in df.iterrows():
             # Handle potential non-string data gracefully before .str methods
            row_values = []
            for item in row:
                try:
                    row_values.append(str(item).lower())
                except:
                    row_values.append("") # Append empty string if conversion fails

            # Check for 'region' and at least one grade indicator
            has_region = any('region' in cell for cell in row_values)
            has_grade = any(any(grade.lower() in cell for cell in row_values) for grade in ['kindergarten', 'grade 1', 'g1', 'g2', 'g3']) # Broader check

            if has_region and has_grade:
                 header_row_index = idx
                 break

        if header_row_index is None:
             raise ValueError("Could not find a valid header row containing 'Region' and grade indicators.")

        # --- Split based on detected level (School vs Regional/Divisional etc.) ---
        header_content = df.iloc[header_row_index].astype(str).str.upper()
        is_school_level = 'SCHOOL NAME' in header_content.values and 'BEIS SCHOOL ID' in header_content.values

        # Assign header AFTER determining level, as logic differs
        df.columns = df.iloc[header_row_index]
        df_data_part = df.iloc[header_row_index + 1:].reset_index(drop=True)
        # Attempt numeric conversion early where possible
        df_data_part = df_data_part.apply(pd.to_numeric, errors='ignore')


        if is_school_level:
            print("--- Cleaning School Level File ---")
            df_cleaned = df_data_part # Start with the data part
            # Ensure essential columns exist before applying school logic
            required_school_cols = ['School Name', 'BEIS School ID', 'Region'] # Add others if needed
            if not all(col in df_cleaned.columns for col in required_school_cols):
                 raise ValueError("School level file missing essential columns like 'School Name' or 'BEIS School ID'.")

            # Apply school-specific cleaning (your existing logic)
            special_cases = {
                # ... your special_cases dictionary ...
                r'\bES\b': 'ELEMENTARY SCHOOL', 'E/S': 'ELEMENTARY SCHOOL', r'\bELEM\b': 'ELEMENTARY SCHOOL', # Use \b for word boundaries
                r'\bNHS\b': 'NATIONAL HIGH SCHOOL', r'\bHS\b': 'HIGH SCHOOL', r'\bCES\b': 'CENTRAL ELEMENTARY SCHOOL',
                r'\bSCH\b': 'SCHOOL', r'Incorporated': 'INC.', r'\bMEM\b': 'MEMORIAL', # Corrected MEM regex
                r'\bCS\b': 'CENTRAL SCHOOL', r'\bPS\b': 'PRIMARY SCHOOL', 'P/S': 'PRIMARY SCHOOL',
                r'\bLC\b': 'LEARNING CENTER', r'BARANGAY': 'BRGY.', r'POBLACION': 'POB.', # Simpler replacement
                r'STREET': 'ST.', r'BUILDING': 'BLDG.', r'BLOCK': 'BLK.', r'PUROK': 'PRK.',
                r'AVENUE': 'AVE.', r'ROAD': 'RD.', r'PACKAGE': 'PKG.', r'PHASE': 'PH.',
                 # Careful with these general ones, apply last
                 r'\s*,\s*': ', ', r'\s{2,}': ' '
            }
            # Ensure columns exist before formatting
            columns_to_format_text = [col for col in ['School Name', 'Street Address', 'Province', 'Municipality', 'Barangay'] if col in df_cleaned.columns]
            if columns_to_format_text:
                 df_cleaned[columns_to_format_text] = df_cleaned[columns_to_format_text].astype(str).apply(
                     lambda x: x.str.replace('#', '', regex=False)
                                .str.replace(r'^[-:]+', '', regex=True) # Match one or more at the start
                                .str.strip()
                                .str.upper()
                                # Apply regex replacements carefully
                                .replace(special_cases, regex=True)
                 )

            columns_to_format_na = [col for col in ['Street Address', 'Barangay'] if col in df_cleaned.columns]
            if columns_to_format_na:
                na_values_list = ['N/A', 'N.A.', 'N / A', 'NA', 'NONE', 'NULL', 'NOT APPLICABLE', '', '0', '_', '=', '.', '-----']
                df_cleaned[columns_to_format_na] = df_cleaned[columns_to_format_na].replace(na_values_list, np.nan) # Use numpy nan
                df_cleaned[columns_to_format_na] = df_cleaned[columns_to_format_na].replace(r'^[\s\W_]+$', np.nan, regex=True) # Match whitespace/non-word chars only
                df_cleaned[columns_to_format_na] = df_cleaned[columns_to_format_na].fillna("UNKNOWN") # Fill actual NaNs

            # Standardize numeric columns (enrollment)
            non_enrollment_cols_school = [
                'Region', 'Division', 'District', 'BEIS School ID', 'School Name',
                'Street Address', 'Province', 'Municipality', 'Legislative District',
                'Barangay', 'Sector', 'School Subclassification', 'School Type', 'Modified COC' # Add any others
            ]
            enrollment_cols = [col for col in df_cleaned.columns if col not in non_enrollment_cols_school and col in standard_columns]

            # Convert enrollment columns to numeric, coercing errors, filling NaN with 0
            for col in enrollment_cols:
                if col in df_cleaned.columns:
                    df_cleaned[col] = df_cleaned[col].astype(str).str.replace(',', '', regex=False) # Remove commas
                    df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')

            # Filter unrealistic data AFTER conversion
            df_cleaned = df_cleaned.fillna({col: 0 for col in enrollment_cols}) # Fill NaN with 0 only for enrollment cols
             # Now convert to integer type
            for col in enrollment_cols:
                if col in df_cleaned.columns:
                    try:
                        df_cleaned[col] = df_cleaned[col].astype(int)
                    except (ValueError, TypeError) as e:
                         print(f"Warning: Could not convert column '{col}' to int after cleaning. Error: {e}")
                         # Decide how to handle - leave as float, try object, or raise error?
                         # df_cleaned[col] = df_cleaned[col].astype(object) # Option: keep as object


            max_threshold = 5000 # Define threshold

            # Identify rows to drop based on conditions on numeric enrollment columns
            unrealistic_indices = set()
            for col in enrollment_cols:
                 if col in df_cleaned.columns:
                     # Check for negative values
                     unrealistic_indices.update(df_cleaned[df_cleaned[col] < 0].index)
                     # Check for values above threshold
                     unrealistic_indices.update(df_cleaned[df_cleaned[col] > max_threshold].index)
                     # Note: Check for non-integers isn't needed if successfully converted to int

            # Drop unrealistic rows
            df_cleaned = df_cleaned.drop(list(unrealistic_indices))


        else:
            # --- REGIONAL/OTHER LEVEL FILE CLEANING (Original Logic Branch) ---
            print("--- Cleaning Regional/Other Level File ---")
            # Assume multi-level header structure for raw regional files
            # Need to re-read the relevant header part from the original df before data_part was made
            # This part needs careful handling of raw files structure
            
            # It's safer to work from the raw df for header reconstruction
            # Assuming header_row_index points to the 'Grade' level row
            if header_row_index + 1 >= len(df):
                 raise ValueError("File structure invalid: Expected at least two header rows below the identified start.")

            grade_row_series = df.iloc[header_row_index]
            gender_row_series = df.iloc[header_row_index + 1] # Assumes gender is directly below grade

            new_columns = []
            last_valid_grade = None
            gender_indicators = ['MALE', 'FEMALE'] # Use uppercase standard

            col_idx = 0
            while col_idx < len(grade_row_series):
                grade_val = str(grade_row_series.iloc[col_idx]).strip()
                gender_val = str(gender_row_series.iloc[col_idx]).strip().upper()

                if grade_val and grade_val.upper() != 'NAN':
                    last_valid_grade = preprocess_column(grade_val) # Preprocess grade part
                    # If the grade cell itself contains gender, it might be a merged cell or single col header
                    combined_header = f"{last_valid_grade}"
                    
                    # Check if the corresponding gender cell indicates a gender
                    if gender_val in gender_indicators:
                         combined_header = f"{last_valid_grade} {gender_val.title()}"
                    # Else: Assume it's a total or non-gendered column for that grade
                    
                    new_columns.append(standardize_column_name(combined_header))
                    col_idx += 1

                elif last_valid_grade: # Current grade cell is empty, use last valid grade
                     # Check if the gender cell provides the necessary info
                     if gender_val in gender_indicators:
                          combined_header = f"{last_valid_grade} {gender_val.title()}"
                          new_columns.append(standardize_column_name(combined_header))
                          col_idx += 1
                     else:
                          # Ambiguous case: empty grade, non-standard gender cell.
                          # Maybe skip or use a placeholder? Or assume it belongs to the previous grade's total?
                          # Let's append a placeholder and move on. Could indicate data issue.
                          # new_columns.append(f"UNKNOWN_{col_idx}")
                          # Or try to use the value from the gender row as header if non-empty
                          if gender_val and gender_val != 'NAN':
                                new_columns.append(standardize_column_name(gender_val)) # Use gender row value directly
                          else:
                                new_columns.append(f"UNKNOWN_{col_idx}") # Placeholder
                          col_idx += 1
                else:
                     # No current grade and no previous grade (e.g., leading empty columns)
                     # Use the value from the gender row if available, otherwise placeholder
                     header_val = gender_val if gender_val and gender_val != 'NAN' else f"UNKNOWN_{col_idx}"
                     # Special check for 'Region' which might be in the 'gender' row position
                     if header_val.upper() == 'REGION':
                         new_columns.append('Region')
                     else:
                         new_columns.append(standardize_column_name(header_val))
                     col_idx += 1


            # Data starts 2 rows below the grade header row
            df_data = df.iloc[header_row_index + 2:].reset_index(drop=True)

            # Check column length mismatch
            if len(new_columns) != df_data.shape[1]:
                 print(f"Warning: Number of generated columns ({len(new_columns)}) does not match number of data columns ({df_data.shape[1]}). Adjusting.")
                 # Simple fix: truncate or pad new_columns. Truncating is safer if extra cols were generated.
                 min_len = min(len(new_columns), df_data.shape[1])
                 new_columns = new_columns[:min_len]
                 df_data = df_data.iloc[:, :min_len]


            df_data.columns = new_columns
            df_data = df_data.dropna(how='all') # Drop rows where ALL values are NaN
            df_data = df_data.replace(['-', '--', ' - '], '0', regex=False) # Replace specific markers with '0'

            df_cleaned = df_data

            # Standardize numeric columns (enrollment)
            non_enrollment_cols_regional = ['Region'] # Potentially others like 'Division' if present
            enrollment_cols = [col for col in df_cleaned.columns if col not in non_enrollment_cols_regional and col in standard_columns]

            for col in enrollment_cols:
                if col in df_cleaned.columns:
                    df_cleaned[col] = df_cleaned[col].astype(str).str.replace(',', '', regex=False).str.strip()
                    df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce').fillna(0).astype(int)

            # Ensure 'Region' column is standardized if it exists after header processing
            if 'Region' in df_cleaned.columns:
                df_cleaned['Region'] = df_cleaned['Region'].apply(standardize_region_values)


    # --- Final Save ---
    if not df_cleaned.empty:
        # Construct filename and path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        input_basename = os.path.splitext(os.path.basename(file_path))[0]
        cleaned_filename = f"{input_basename}_cleaned_{timestamp}.csv"
        cleaned_path = os.path.join(cleaned_files_directory, cleaned_filename)
        
        # Save the cleaned DataFrame
        df_cleaned.to_csv(cleaned_path, index=False)
        print(f"Cleaned file saved to: {cleaned_path}")
        return cleaned_path
    else:
        print("Warning: Cleaned DataFrame is empty. No file saved.")
        return None # Indicate that no file was saved


# Example Usage (assuming you have a file 'my_regional_data.csv'):
# try:
#     cleaned_file_path = clean_data('my_regional_data.csv')
#     if cleaned_file_path:
#         print(f"Processing successful: {cleaned_file_path}")
#     else:
#         print("Processing resulted in no file.")
# except ValueError as e:
#     print(f"Data processing failed: {e}")
# except FileNotFoundError:
#     print("Error: Input file not found.")
# except Exception as e:
#     print(f"An unexpected error occurred: {e}")