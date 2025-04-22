import os
import pandas as pd
import re

def get_dataset_path(filename="Cleaned_School_DataSet.csv"):
    return os.path.join(os.path.dirname(__file__), 'static', filename)

def fetch_enrollment_records_from_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return df.to_dict(orient='records')
    except FileNotFoundError as e:
        print(f"Error: File not found at {file_path}: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def fetch_summary_data_from_csv(file_path):
    try:
        df = pd.read_csv(file_path)

        # Normalize column names
        df.columns = df.columns.str.strip().str.replace('–', '-', regex=False).str.replace('—', '-', regex=False)

        summary = {}

        # Male/female/total enrollments
        try:
            male_cols = [col for col in df.columns if re.search(r'\bmale\b', col, re.IGNORECASE)]
            female_cols = [col for col in df.columns if re.search(r'\bfemale\b', col, re.IGNORECASE)]

            for col in male_cols + female_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['TotalMale'] = df[male_cols].sum(axis=1)
            df['TotalFemale'] = df[female_cols].sum(axis=1)
            df['TotalEnrollment'] = df['TotalMale'] + df['TotalFemale']

            summary['maleEnrollments'] = int(df['TotalMale'].sum())
            summary['femaleEnrollments'] = int(df['TotalFemale'].sum())
            summary['totalEnrollments'] = summary['maleEnrollments'] + summary['femaleEnrollments']
        except Exception as e:
            print(f"Enrollment totals error: {e}")

        # Region & schools
        try:
            region_col = next((col for col in df.columns if col.strip().lower() == 'region'), None)
            summary['regionsWithSchools'] = df[region_col].nunique() if region_col else 0
        except Exception as e:
            print(f"Region processing error: {e}")

        try:
            is_school_level = 'BEIS School ID' in df.columns and 'School Name' in df.columns
            summary['numberOfSchools'] = df['BEIS School ID'].nunique() if is_school_level else None
            summary['numberOfYearLevels'] = 13
        except Exception as e:
            print(f"School info error: {e}")

        try:
            if is_school_level:
                df['UniqueSchool'] = df['School Name'] + " (" + df['BEIS School ID'].astype(str) + ")"
                top_schools = (
                    df.groupby('UniqueSchool')['TotalEnrollment']
                    .sum().sort_values(ascending=False).head(5)
                    .astype(int).to_dict()
                )
                summary['topSchools'] = top_schools
        except Exception as e:
            print(f"Top schools error: {e}")

        try:
            summary['numberOfDivisions'] = df['Division'].nunique()
        except Exception as e:
            print(f"Division error: {e}")

        try:
            summary['numberOfMunicipalities'] = df['Municipality'].nunique()
        except Exception as e:
            print(f"Municipality error: {e}")

        # Enrollment by region
        try:
            if region_col:
                summary['enrollmentByRegion'] = (
                    df.groupby(region_col)['TotalEnrollment'].sum().astype(int).to_dict()
                )
        except Exception as e:
            print(f"Enrollment by region error: {e}")

        # Enrollment by year level
        try:
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
            enrollment_by_year_level = {}
            for grade, columns in grade_columns.items():
                valid_cols = [col for col in columns if col in df.columns]
                enrollment_by_year_level[grade] = int(df[valid_cols].sum().sum()) if valid_cols else 0
            summary['enrollmentByYearLevel'] = enrollment_by_year_level
        except Exception as e:
            print(f"Enrollment by year level error: {e}")

        # Average enrollment per region
        try:
            if region_col and 'BEIS School ID' in df.columns:
                # Clean up and ensure numeric
                df['TotalEnrollment'] = pd.to_numeric(df['TotalEnrollment'], errors='coerce')
                
                # Group by region and school to get total enrollment per school
                school_enrollment = df.groupby(['BEIS School ID', region_col])['TotalEnrollment'].sum().reset_index()

                # Group by region and compute average enrollment across schools
                avg_enrollment = (
                    school_enrollment.groupby(region_col)['TotalEnrollment']
                    .mean()
                    .round(2)
                    .astype(int)
                    .to_dict()
                )

                summary['averageEnrollmentPerRegion'] = avg_enrollment
        except Exception as e:
            print(f"Average enrollment error: {e}")

        # Gender ratio
        try:
            if region_col:
                grouped = df.groupby(region_col)[['TotalMale', 'TotalFemale']].sum()
                grouped['TotalEnrollment'] = grouped['TotalMale'] + grouped['TotalFemale']
                grouped['MalePercentage'] = (grouped['TotalMale'] / grouped['TotalEnrollment']) * 100
                summary['genderRatioByRegion'] = grouped['MalePercentage'].round(2).to_dict()
        except Exception as e:
            print(f"Gender ratio error: {e}")

        # SHS by strand
        try:
            shs_strands = {
                'ABM': ['G11 ACAD - ABM Male', 'G11 ACAD - ABM Female', 'G12 ACAD - ABM Male', 'G12 ACAD - ABM Female'],
                'HUMSS': ['G11 ACAD - HUMSS Male', 'G11 ACAD - HUMSS Female', 'G12 ACAD - HUMSS Male', 'G12 ACAD - HUMSS Female'],
                'STEM': ['G11 ACAD STEM Male', 'G11 ACAD STEM Female', 'G12 ACAD STEM Male', 'G12 ACAD STEM Female'],
                'GAS': ['G11 ACAD GAS Male', 'G11 ACAD GAS Female', 'G12 ACAD GAS Male', 'G12 ACAD GAS Female'],
                'PBM': ['G11 ACAD PBM Male', 'G11 ACAD PBM Female', 'G12 ACAD PBM Male', 'G12 ACAD PBM Female'],
                'TVL': ['G11 TVL Male', 'G11 TVL Female', 'G12 TVL Male', 'G12 TVL Female'],
                'SPORTS': ['G11 SPORTS Male', 'G11 SPORTS Female', 'G12 SPORTS Male', 'G12 SPORTS Female'],
                'ARTS': ['G11 ARTS Male', 'G11 ARTS Female', 'G12 ARTS Male', 'G12 ARTS Female']
            }
            strand_totals = {}
            for strand, cols in shs_strands.items():
                valid_cols = [col for col in cols if col in df.columns]
                strand_totals[strand] = int(df[valid_cols].sum().sum()) if valid_cols else 0
            summary['shsEnrollmentByStrand'] = strand_totals
        except Exception as e:
            print(f"SHS strand error: {e}")

        # Enrollment by sector
        try:
            if 'Sector' in df.columns:
                sector_data = df.groupby('Sector')['TotalEnrollment'].sum()
                summary['enrollmentBySector'] = {
                    sector: int(value) for sector, value in sector_data.items()
                }
        except Exception as e:
            print(f"Enrollment by sector error: {e}")

        return summary

    except Exception as e:
        print(f"Error processing summary data: {e}")
        return {}
    
def get_strand_distribution_by_region(file_path):
    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()

        shs_strands = {
            'ABM': ['G11 ACAD - ABM Male', 'G11 ACAD - ABM Female', 'G12 ACAD - ABM Male', 'G12 ACAD - ABM Female'],
            'HUMSS': ['G11 ACAD - HUMSS Male', 'G11 ACAD - HUMSS Female', 'G12 ACAD - HUMSS Male', 'G12 ACAD - HUMSS Female'],
            'STEM': ['G11 ACAD STEM Male', 'G11 ACAD STEM Female', 'G12 ACAD STEM Male', 'G12 ACAD STEM Female'],
            'GAS': ['G11 ACAD GAS Male', 'G11 ACAD GAS Female', 'G12 ACAD GAS Male', 'G12 ACAD GAS Female'],
            'PBM': ['G11 ACAD PBM Male', 'G11 ACAD PBM Female', 'G12 ACAD PBM Male', 'G12 ACAD PBM Female'],
            'TVL': ['G11 TVL Male', 'G11 TVL Female', 'G12 TVL Male', 'G12 TVL Female'],
            'SPORTS': ['G11 SPORTS Male', 'G11 SPORTS Female', 'G12 SPORTS Male', 'G12 SPORTS Female'],
            'ARTS': ['G11 ARTS Male', 'G11 ARTS Female', 'G12 ARTS Male', 'G12 ARTS Female']
        }

        region_col = next((col for col in df.columns if col.lower() == 'region'), None)
        if not region_col:
            return {}

        result = {}
        for strand, cols in shs_strands.items():
            valid_cols = [col for col in cols if col in df.columns]
            if not valid_cols:
                continue
            grouped = df.groupby(region_col)[valid_cols].sum().sum(axis=1)
            result[strand] = grouped

        heatmap_df = pd.DataFrame(result).fillna(0).astype(int)
        heatmap_df = heatmap_df.reset_index().rename(columns={region_col: 'Region'})
        return heatmap_df.to_dict(orient='list')

    except Exception as e:
        print(f"Error generating strand-region heatmap: {e}")
        return {}

