import os
import pandas as pd
from datetime import datetime
import re
from difflib import get_close_matches

standard_columns = [
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
    'barmm': 'BARMM',
    'bangsamoro': 'BARMM',
    'car': 'CAR',
    'cordillera': 'CAR',
    'caraga': 'CARAGA',
    'mimaropa': 'MIMAROPA',
    'ncr': 'NCR',
    'national capital region': 'NCR',
    'pso': 'PSO',
    'region i': 'Region I', 'region 1': 'Region I',
    'region ii': 'Region II', 'region 2': 'Region II',
    'region iii': 'Region III', 'region 3': 'Region III',
    'region iv-a': 'Region IV-A', 'region 4a': 'Region IV-A', 'region iva': 'Region IV-A',
    'region v': 'Region V', 'region 5': 'Region V',
    'region vi': 'Region VI', 'region 6': 'Region VI',
    'region vii': 'Region VII', 'region 7': 'Region VII',
    'region viii': 'Region VIII', 'region 8': 'Region VIII',
    'region ix': 'Region IX', 'region 9': 'Region IX',
    'region x': 'Region X', 'region 10': 'Region X',
    'region xi': 'Region XI', 'region 11': 'Region XI',
    'region xii': 'Region XII', 'region 12': 'Region XII',
}

def standardize_region_values(val):
    if isinstance(val, str):
        val_lower = val.strip().lower()
        
        # Try to extract short region codes using regex
        match = re.search(r'(region\s?[ixv0-9\-a]+|ncr|caraga|car|barmm|pso)', val_lower)
        if match:
            code = match.group(1).replace(" ", "").replace("-", "").lower()
            for key, standard in region_mapping.items():
                if key.replace(" ", "").replace("-", "") == code:
                    return standard
        return val.strip()
    return val


def preprocess_column(col):
    col = str(col).upper().strip()

    if any(keyword in col for keyword in ['JHS', 'ES', 'ELEM']):
        # Replace 'Non-Grade' or variations with 'NG'
        col = re.sub(r'NON\s*[-–]?\s*GRADE', 'NG', col)
        col = re.sub(r'\bJHS\b(?!\s*NG)', 'JHS NG', col)  
        col = re.sub(r'\bES\b(?!\s*NG)', 'ELEM NG', col)  
        col = re.sub(r'\bELEM\b(?!\s*NG)', 'Elem NG', col) 
    
    # Further standardization rules
    col = re.sub(r'ARTS\s*&\s*DESIGN', 'ARTS', col)
    col = re.sub(r'G(\d{1,2})\s+(MALE|FEMALE)', r'G\1 \2', col)
    col = re.sub(r'KINDERGARTEN', 'K', col)
    col = re.sub(r'G11\s+(ABM|HUMSS|STEM|GAS|MARITIME|PBM)', r'G11 ACAD - \1', col)
    col = re.sub(r'G12\s+(ABM|HUMSS|STEM|GAS|MARITIME|PBM)', r'G12 ACAD - \1', col)
    
    col = re.sub(r'^\s*', '', col)
    col = re.sub(r'\s{2,}', ' ', col)
    
    return col

def standardize_column_name(col):
    col = preprocess_column(col)
    col = col.replace('K Male', 'Kindergarten Male').replace('K Female', 'Kindergarten Female')
    col = re.sub(r'\bG(\d{1,2})\b', lambda m: f'Grade {int(m.group(1))}', col)
    col = re.sub(r'^(Male|Female)\s+', '', col)
    col = re.sub(r'\s+(Male|Female)$', r' \1', col)
    col = re.sub(r'\((.*?)\)', r'\1', col)
    col = re.sub(r'\s*-\s*', ' - ', col)
    col = re.sub(r'\s{2,}', ' ', col).strip()

    parts = col.split()
    col = ' '.join(part.capitalize() if part.upper() not in ['TVL', 'STEM', 'ABM', 'HUMSS', 'GAS', 'PBM', 'NG', 'JHS'] else part.upper() for part in parts)
    col = col.replace("Kindergarten", "K")
    col = re.sub(r'Grade (\d{1,2})', r'G\1', col)

    # Match to closest valid column
    match = get_close_matches(col, standard_columns, n=1, cutoff=0.85)
    return match[0] if match else col

    
def clean_data(file_path):
    df = pd.read_csv(file_path, header=None)
    cleaned_files_directory = os.path.join(os.path.dirname(__file__), 'cleaned_files')
    os.makedirs(cleaned_files_directory, exist_ok=True)
    df = df.applymap(standardize_region_values)

    # Detect header row
    potential_headers = ['Region', 'Kindergarten', 'Grade 1', 'Grade 2', 'G1', 'G2']
    header_row_index = None

    for idx, row in df.iterrows():
        row_values = row.astype(str).str.lower().tolist()
        if all(any(keyword.lower() in cell for cell in row_values) for keyword in ['region']) and \
           any(any(grade.lower() in cell for cell in row_values) for grade in ['kindergarten', 'grade 1', 'g1']):
            header_row_index = idx
            break

    if header_row_index is None:
        raise ValueError("Could not find a valid header row.")

    df.columns = df.iloc[header_row_index]
    df_cleaned = df.iloc[header_row_index + 1:].reset_index(drop=True)
    df_cleaned = df_cleaned.apply(pd.to_numeric, errors='ignore')
    
    is_school_level = 'School Name' in df_cleaned.columns and 'BEIS School ID' in df_cleaned.columns

    if is_school_level:
        # School-level logic
        special_cases = {
            r'\bES\b': 'ELEMENTARY SCHOOL', 'E/S': 'ELEMENTARY SCHOOL', r'\bELEM.\b': 'ELEMENTARY SCHOOL',
            r'\bNHS\b': 'NATIONAL HIGH SCHOOL', r'\bHS\b': 'HIGH SCHOOL', r'\bCES\b': 'CENTRAL ELEMENTARY SCHOOL',
            r'\bSCH.\b': 'SCHOOL', 'Incorporated': 'INC.', r'\bMEM.\b': 'MEMORIAL',
            r'\bCS\b': 'CENTRAL SCHOOL', r'\bPS\b': 'PRIMARY SCHOOL', 'P/S': 'PRIMARY SCHOOL',
            r'\bLC\b': 'LEARNING CENTER', 'BARANGAY': 'BRGY. ', 'POBLACION': 'POB. ',
            'STREET': 'ST. ', 'BUILDING': 'BLDG. ', 'BLOCK': 'BLK. ', 'PUROK': 'PRK. ',
            'AVENUE': 'AVE. ', 'ROAD': 'RD. ', 'PACKAGE': 'PKG. ', 'PHASE': 'PH. ',
            r'\s*,\s*': ', ', r'\s{2,}': ' '
        }

        columns_to_format = ['School Name', 'Street Address', 'Province', 'Municipality', 'Barangay']
        df_cleaned[columns_to_format] = df_cleaned[columns_to_format].apply(
            lambda x: x.str.replace('#', '', regex=False)
                        .str.replace(r'^[-:]', '', regex=True)
                        .str.strip()
                        .str.upper()
                        .replace(special_cases, regex=True)
        )

        columns_to_format = ['Street Address', 'Barangay']
        df_cleaned[columns_to_format] = (
            df_cleaned[columns_to_format]
            .replace(['N/A', 'N.A.', 'N / A', 'NA', 'NONE', 'NULL', 'NOT APPLICABLE', '', '0', '_', '=', '.', '-----'], pd.NA)
            .replace(r'^[\s\W_]+$', pd.NA, regex=True)
            .fillna("UNKNOWN")
        )

        non_enrollment_cols = [
            'Region', 'Division', 'District', 'BEIS School ID', 'School Name',
            'Street Address', 'Province', 'Municipality', 'Legislative District',
            'Barangay', 'Sector', 'School Subclassification', 'School Type', 'Modified COC'
        ]

        enrollment_cols = [col for col in df_cleaned.columns if col not in non_enrollment_cols]
        max_threshold = 5000

        unrealistic_data = df_cleaned[(
            df_cleaned[enrollment_cols] < 0).any(axis=1) |
            (df_cleaned[enrollment_cols] % 1 != 0).any(axis=1) |
            (df_cleaned[enrollment_cols] > max_threshold).any(axis=1)
        ]

        df_cleaned = df_cleaned.drop(unrealistic_data.index)

    else:
        # Regional-level logic
        non_enrollment_cols = ['Region']
        df_trimmed = df.iloc[header_row_index:].reset_index(drop=True)

        grade_row = df_trimmed.iloc[0].tolist()
        gender_row = df_trimmed.iloc[1].tolist()

        new_columns = []
        last_valid_grade = None
        gender_indicators = ['male', 'female', 'm', 'f']


        for i in range(len(gender_row)):
            grade = str(grade_row[i]).strip() if i < len(grade_row) else ""
            gender = str(gender_row[i]).strip() if i < len(gender_row) else ""

            if grade.lower() == 'region':
                new_columns.append('Region')
                continue

            if grade and grade.lower() != 'nan':
                last_valid_grade = grade
            elif not grade or grade.lower() == 'nan':
                grade = last_valid_grade

            if gender.lower() in gender_indicators:
                new_columns.append(f"{grade} {gender.title()}")
            else:
                new_columns.append(grade)

        df_data = df_trimmed.iloc[2:].reset_index(drop=True)
        df_data.columns = new_columns
        df_data = df_data.dropna(how='all')
        df_data = df_data.replace('-', '0')
        df_cleaned = df_data

        enrollment_cols = [col for col in df_cleaned.columns if col not in non_enrollment_cols]

        df_cleaned.rename(columns={col: standardize_column_name(col) for col in enrollment_cols}, inplace=True)

        enrollment_cols = [col for col in df_cleaned.columns if col not in non_enrollment_cols]

        for col in enrollment_cols:
            df_cleaned[col] = df_cleaned[col].astype(str).str.replace(',', '').str.strip()
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce').fillna(0).astype(int)
            
    # Save cleaned file
    cleaned_filename = f"cleaned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    cleaned_path = os.path.join(cleaned_files_directory, cleaned_filename)
    df_cleaned.to_csv(cleaned_path, index=False)
    return cleaned_path