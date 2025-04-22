# ~~~ Import statements remain the same ~~~
from dash import Dash, html, dcc, Input, Output, State, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from data_config import get_dataset_path, fetch_enrollment_records_from_csv, fetch_summary_data_from_csv
import io
import base64
import re
import numpy as np

GENDER_COLORS = {'Male': '#1f77b4', 'Female': '#e377c2', 'Unknown': '#888'}
QUALITATIVE_COLOR_SEQUENCE = px.colors.qualitative.Pastel
PLOT_TEMPLATE = "plotly_white"

def create_dash_app_report(flask_app):
    dash_app_report = Dash(__name__, server=flask_app, routes_pathname_prefix="/dashreport/", external_stylesheets=['assets/style.css'], suppress_callback_exceptions=True, serve_locally=True)

    df_all = pd.DataFrame() # Initialize empty DataFrame
    enrollment_cols = [] # Initialize empty list

    try:
        file_path = get_dataset_path()
        all_data = fetch_enrollment_records_from_csv(file_path)
        df_all = pd.DataFrame(all_data)

        enrollment_patterns = ['K ', 'G1 ', 'G2 ', 'G3 ', 'G4 ', 'G5 ', 'G6 ', 'G7 ', 'G8 ', 'G9 ', 'G10 ', 'G11 ', 'G12 ', 'Elem NG ', 'JHS NG ']
        enrollment_cols = [
            col for col in df_all.columns
            if any(col.startswith(pattern) for pattern in enrollment_patterns)
            and (' Male' in col or ' Female' in col)
        ]

        for col in enrollment_cols:
            if col in df_all.columns:
                # Use errors='coerce' to turn non-numeric into NaN
                df_all[col] = pd.to_numeric(df_all[col], errors='coerce')
        # Fill NaN with 0 and convert to integer after coercion
        df_all[enrollment_cols] = df_all[enrollment_cols].fillna(0).astype(int)


        id_cat_cols = ['BEIS School ID', 'Region', 'Division', 'Sector', 'School Type', 'School Subclassification', 'Municipality', 'Legislative District', 'School Name']
        for col in id_cat_cols:
             if col in df_all.columns:
                 df_all[col] = df_all[col].astype(str).fillna('Unknown')

    except FileNotFoundError:
        print(f"Error: Data file not found at {file_path}")
        dash_app_report.layout = html.Div([html.H1("Error"), html.P(f"Enrollment data file not found at {file_path}.")])
        return dash_app_report
    except Exception as e:
        print(f"Error loading or processing data: {e}")
        dash_app_report.layout = html.Div([html.H1("Error"), html.P(f"An error occurred: {e}")])
        return dash_app_report

    # --- Data Processing for Filters (moved after data loading checks) ---
    regions = sorted([r for r in df_all["Region"].unique() if r != 'Unknown']) if "Region" in df_all.columns and not df_all.empty else []
    divisions_by_region = {}
    all_divisions = []
    if "Region" in df_all.columns and "Division" in df_all.columns and not df_all.empty:
        df_filtered_for_divisions = df_all[(df_all["Region"] != 'Unknown') & (df_all["Division"] != 'Unknown')]
        if not df_filtered_for_divisions.empty:
             divisions_by_region = df_filtered_for_divisions.groupby("Region")["Division"].unique().apply(lambda x: sorted(list(x))).to_dict()
             all_divisions = sorted(df_filtered_for_divisions["Division"].unique())

    all_beis_ids = []
    if "BEIS School ID" in df_all.columns and "School Name" in df_all.columns and not df_all.empty:
        unique_schools = df_all[["BEIS School ID", "School Name"]].drop_duplicates(subset=['BEIS School ID'])
        if not unique_schools.empty:
            all_beis_ids_with_names = sorted(unique_schools.set_index("BEIS School ID")["School Name"].to_dict().items())
            # Truncate long names and filter out 'Unknown' ID
            all_beis_ids = [{'label': f"{id_} - {name[:50]}{'...' if len(name)>50 else ''}", 'value': id_} for id_, name in all_beis_ids_with_names if id_ != 'Unknown']


    grades = ['K'] + [f'G{i}' for i in range(1, 11)] + ['G11', 'G12']
    sector_types = sorted([s for s in df_all["Sector"].unique() if s != 'Unknown']) if "Sector" in df_all.columns and not df_all.empty else []


    # --- DASH LAYOUT (Width adjusted) ---
    dash_app_report.layout = html.Div([
        html.H1("📊 School Enrollment Dashboard", style={
            "textAlign": "center",
            "marginBottom": "20px",
            "color": "#333",
            "fontSize": "2rem"
        }),

        html.Div([
            html.Div([
                html.Label("🔍 Region"),
                dcc.Dropdown(id='region-filter', options=[{'label': r, 'value': r} for r in regions], value=None, placeholder="Select Region") # Added options and default value
            ], className="filter-item"),

            html.Div([
                html.Label("📍 Division"),
                dcc.Dropdown(id='division-filter', options=[{'label': d, 'value': d} for d in all_divisions], value=None, placeholder="Select Division", disabled=False) # Added options and default value, enabled by default
            ], className="filter-item"),

            html.Div([
                html.Label("🎓 Grade Level"),
                dcc.Dropdown(id='grade-filter', options=[{'label': g, 'value': g} for g in grades], value=None, placeholder="Select Grade Level") # Added options and default value
            ], className="filter-item"),

            html.Div([
                html.Label("🏫 Sector"),
                dcc.RadioItems(id='sector-filter', options=[{'label': s, 'value': s} for s in sector_types], value=None, inline=True) # Added options and default value
            ], className="filter-item"),

            html.Div([
                html.Label("🔑 School (BEIS ID)"),
                dcc.Dropdown(id='beis-id-filter', options=all_beis_ids, value=None, placeholder="Select School (Optional)") # Added options and default value
            ], className="filter-item filter-item-wide"),
        ], className="filters-container"),

        html.Div([
            html.Button("Reset Filters", id="reset-button", n_clicks=0, className="reset-button"),
            html.Button("⬇ Download Data", id="btn-download", n_clicks=0, className="download-button"),
        ], style={"display": "flex", "justifyContent": "center", "margin": "15px 0"}),

        html.Hr(),

        dcc.Loading(id="loading-kpi", type="circle", children=html.Div(id='kpi-cards', className="kpi-cards-container")),

        html.Hr(),

        html.H2("Overview Analysis", style={"textAlign": "center", "marginBottom": "15px", "color": "#555"}),

        html.Div(className="row", children=[
            dcc.Loading(type="circle", children=dcc.Graph(id='region-enrollment-bar', className="graph-item-half")),
            dcc.Loading(type="circle", children=dcc.Graph(id='grade-gender-parity-bar', className="graph-item-half")),
        ]),

        html.Div(className="row", children=[
            dcc.Loading(type="circle", children=dcc.Graph(id='sector-distribution', className="graph-item-half")),
            dcc.Loading(type="circle", children=dcc.Graph(id='education-stage-distribution', className="graph-item-half")),
        ]),

        html.Div(className="row", children=[
            dcc.Loading(type="circle", children=dcc.Graph(id='shs-strand-gender-combined-bar', className="graph-item-half")),
            dcc.Loading(type="circle", children=dcc.Graph(id='strand-enrollment-trend-line', className="graph-item-half")),
        ]),

        html.Div(className="row", children=[
            dcc.Loading(type="circle", children=dcc.Graph(id='top-populated-schools-bar', className="graph-item-half")),
            dcc.Loading(type="circle", children=dcc.Graph(id='schools-offering-strand-treemap', className="graph-item-half")),
        ]),

        html.Hr(style={"marginTop": "25px", "marginBottom": "15px"}),

        html.H2("⚠️ Watchlist: Least Populated Schools", style={"textAlign": "center", "marginBottom": "12px", "color": "#E69F00"}),

        dcc.Loading(id="loading-table", type="circle", children=html.Div(id='flagged-schools-table', className="table-container")),

        html.Br(),

        dcc.Download(id="download-data")

    ], className="main-container", style={
        "backgroundColor": "#f0f2f5",
        "padding": "40px",
        "maxWidth": "1200px",
        "margin": "20px auto"
    })

    @dash_app_report.callback(
        Output('division-filter', 'options'),
        Output('division-filter', 'disabled'),
        Input('region-filter', 'value')
    )
    def update_divisions_dropdown(selected_region):
        if selected_region and selected_region != 'Unknown':
            options = [{'label': d, 'value': d} for d in divisions_by_region.get(selected_region, [])]
            return options, False
        return [{'label': d, 'value': d} for d in all_divisions], False

    # Callback to update BEIS School ID options based on selected Region (and implicitly Division if Region is selected)
    @dash_app_report.callback(
        Output('beis-id-filter', 'options'),
        Input('region-filter', 'value'),
        Input('division-filter', 'value'),
    )
    def update_beis_ids_dropdown(selected_region, selected_division):
        filtered_schools_df = df_all.copy()

        if selected_region and selected_region != 'Unknown':
            filtered_schools_df = filtered_schools_df[filtered_schools_df['Region'] == selected_region]
        if selected_division and selected_division != 'Unknown':
            filtered_schools_df = filtered_schools_df[filtered_schools_df['Division'] == selected_division]

        beis_ids_with_names_filtered = []
        if 'BEIS School ID' in filtered_schools_df.columns and 'School Name' in filtered_schools_df.columns and not filtered_schools_df.empty:
             unique_filtered_schools = filtered_schools_df[["BEIS School ID", "School Name"]].drop_duplicates(subset=['BEIS School ID'])
             beis_ids_with_names_filtered = sorted(unique_filtered_schools.set_index("BEIS School ID")["School Name"].to_dict().items())
             beis_ids_with_names_filtered = [{'label': f"{id_} - {name[:50]}{'...' if len(name)>50 else ''}", 'value': id_} for id_, name in beis_ids_with_names_filtered if id_ != 'Unknown']

        return beis_ids_with_names_filtered if beis_ids_with_names_filtered else all_beis_ids


    # Reset Filters Callback
    @dash_app_report.callback(
        Output('region-filter', 'value', allow_duplicate=True),
        Output('division-filter', 'value', allow_duplicate=True),
        Output('grade-filter', 'value', allow_duplicate=True),
        Output('sector-filter', 'value', allow_duplicate=True),
        Output('beis-id-filter', 'value', allow_duplicate=True),
        Input('reset-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def reset_filters(n_clicks):
        return None, None, None, None, None


    # --- Main Update Callback ---
    @dash_app_report.callback(
        Output('kpi-cards', 'children'),
        Output('region-enrollment-bar', 'figure'),
        Output('grade-gender-parity-bar', 'figure'),
        Output('sector-distribution', 'figure'),
        Output('education-stage-distribution', 'figure'),
        Output('shs-strand-gender-combined-bar', 'figure'),
        Output('top-populated-schools-bar', 'figure'),
        Output('strand-enrollment-trend-line', 'figure'),
        Output('schools-offering-strand-treemap', 'figure'),
        Output('flagged-schools-table', 'children'),
        Input('region-filter', 'value'),
        Input('division-filter', 'value'),
        Input('grade-filter', 'value'),
        Input('sector-filter', 'value'),
        Input('beis-id-filter', 'value'),
    )
    def update_dashboard(selected_region, selected_division, selected_grade, selected_sector, selected_beis_id):

        # --- Filtering Logic ---
        filtered_df = df_all.copy()
        query_parts = []
        if selected_region and selected_region != 'Unknown': query_parts.append(f"Region == '{selected_region}'")
        if selected_division and selected_division != 'Unknown': query_parts.append(f"Division == '{selected_division}'")
        if selected_sector and selected_sector != 'Unknown': query_parts.append(f"Sector == '{selected_sector}'")
        if selected_beis_id and selected_beis_id != 'Unknown': query_parts.append(f"`BEIS School ID` == '{str(selected_beis_id)}'")

        if query_parts:
             filtered_df = filtered_df.query(" and ".join(query_parts))

        filtered_df_base_after_geo_sector_id = filtered_df.copy()

        current_enrollment_cols = list(enrollment_cols)
        if selected_grade:
            grade_columns_to_keep = []
            for col in enrollment_cols:
                if col in filtered_df.columns:
                    if col.startswith(selected_grade + " ") or (selected_grade == 'K' and col.startswith('K ')):
                        grade_columns_to_keep.append(col)
            current_enrollment_cols = grade_columns_to_keep

        numeric_enrollment_cols_filtered = [
            col for col in current_enrollment_cols
            if col in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df[col])
        ]
        all_numeric_enrollment_cols_in_base = [
             col for col in enrollment_cols
             if col in filtered_df_base_after_geo_sector_id.columns and pd.api.types.is_numeric_dtype(filtered_df_base_after_geo_sector_id[col])
        ]


        # KPIs Calculation
        total_enrollments = filtered_df[numeric_enrollment_cols_filtered].sum().sum() if numeric_enrollment_cols_filtered and not filtered_df.empty else 0
        male_enrollments = filtered_df[[col for col in numeric_enrollment_cols_filtered if 'Male' in col]].sum().sum() if numeric_enrollment_cols_filtered and not filtered_df.empty else 0
        female_enrollments = filtered_df[[col for col in numeric_enrollment_cols_filtered if 'Female' in col]].sum().sum() if numeric_enrollment_cols_filtered and not filtered_df.empty else 0

        # School Count and Most Populated Grade (using base-filtered data)
        number_of_schools = filtered_df_base_after_geo_sector_id['BEIS School ID'].nunique() if 'BEIS School ID' in filtered_df_base_after_geo_sector_id.columns and not filtered_df_base_after_geo_sector_id.empty else 0
        most_populated_grade = "N/A"
        if not filtered_df_base_after_geo_sector_id.empty and all_numeric_enrollment_cols_in_base:
            grade_enrollment_base = {}
            for col in all_numeric_enrollment_cols_in_base:
                match = re.match(r'(K|G\d{1,2}|Elem NG|JHS NG)\b', col)
                if match:
                    grade = match.group(1)
                    grade_enrollment_base[grade] = grade_enrollment_base.get(grade, 0) + filtered_df_base_after_geo_sector_id[col].sum()
            ordered_grades_keys = ['K'] + [f'G{i}' for i in range(1, 13)] + ['Elem NG', 'JHS NG']
            present_ordered_grades = [g for g in ordered_grades_keys if g in grade_enrollment_base]

            if grade_enrollment_base:
                 max_enrollment = -1
                 most_populated_grade = "N/A"
                 for grade in present_ordered_grades:
                     if grade in grade_enrollment_base and grade_enrollment_base[grade] > max_enrollment:
                         max_enrollment = grade_enrollment_base[grade]
                         most_populated_grade = grade

        # Placeholder Figure Function - ADDED height=400
        def create_placeholder_figure(title):
             fig = go.Figure()
             fig.add_annotation(text="No data available for this visualization based on current filters.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=12, color="#888"))
             fig.update_layout(title=f"{title}", title_x=0.5, xaxis={'visible': False}, yaxis={'visible': False}, template=PLOT_TEMPLATE, title_font_size=14, height=400, width=600) # Added height
             return fig

        kpis = html.Div([
            html.Div([html.H3("Total Enrolled (Filtered)", className="kpi-title"), html.H1(f"{total_enrollments:,}", className="kpi-value")], className="kpi-card"),
            html.Div([html.H3("Male vs Female (Filtered)", className="kpi-title"), html.P(f"{male_enrollments:,} ♂ | {female_enrollments:,} ♀", className="kpi-value")], className="kpi-card"),
            html.Div([html.H3("Number of Schools", className="kpi-title"), html.H1(f"{number_of_schools:,}", className="kpi-value")], className="kpi-card"),
            html.Div([html.H3("Most Populated Grade", className="kpi-title"), html.H1(most_populated_grade, className="kpi-value")], className="kpi-card"),
        ], className="kpi-cards-container")

        # --- Generate Overview Figures ---

        # 1. Region Enrollment Bar - ADDED height=400
        fig_region_bar = create_placeholder_figure("Total Enrollment by Region")
        region_df_for_chart = df_all if not selected_region else filtered_df_base_after_geo_sector_id
        all_numeric_cols_region = [col for col in enrollment_cols if col in region_df_for_chart.columns and pd.api.types.is_numeric_dtype(region_df_for_chart[col])]

        if 'Region' in region_df_for_chart.columns and not region_df_for_chart.empty and all_numeric_cols_region:
             region_enrollment = region_df_for_chart.groupby("Region")[all_numeric_cols_region].sum().sum(axis=1).reset_index(name='Total Enrollment')
             region_enrollment = region_enrollment[(region_enrollment['Total Enrollment'] > 0) & (region_enrollment['Region'] != 'Unknown')].sort_values('Total Enrollment', ascending=False)
             if not region_enrollment.empty:
                 fig_region_bar = px.bar(region_enrollment, x="Region", y="Total Enrollment", title="Total Enrollment by Region", labels={'Total Enrollment': 'Enrollment Count', 'Region': 'Region'}, template=PLOT_TEMPLATE, color_discrete_sequence=QUALITATIVE_COLOR_SEQUENCE)
                 fig_region_bar.update_layout(title_font_size=14, title_x=0.5, xaxis={'categoryorder':'total descending'}, height=400, width=600) # Added height


        # 2. Grade Gender Parity Bar Chart - ADDED height=400
        fig_grade_gender_parity = create_placeholder_figure("Enrollment by Grade Level and Gender")
        grade_parity_cols = [col for col in numeric_enrollment_cols_filtered if re.match(r'(K|G\d{1,2})\b', col)]

        if grade_parity_cols and not filtered_df.empty:
             melt_df_parity = filtered_df[['BEIS School ID'] + grade_parity_cols] if 'BEIS School ID' in filtered_df.columns else filtered_df[grade_parity_cols]
             melt_id_vars_parity = ['BEIS School ID'] if 'BEIS School ID' in filtered_df.columns else []

             if not melt_id_vars_parity:
                  melt_df_parity['_temp_id'] = range(len(melt_df_parity))
                  melt_id_vars_parity = ['_temp_id']

             melted_parity = pd.melt(melt_df_parity, id_vars=melt_id_vars_parity, value_vars=grade_parity_cols, var_name="GradeGender", value_name="Count")

             if '_temp_id' in melted_parity.columns:
                 melted_parity = melted_parity.drop(columns=['_temp_id'])

             melted_parity = melted_parity[melted_parity['Count'] > 0]

             if not melted_parity.empty:
                 melted_parity["Grade"] = melted_parity["GradeGender"].str.extract(r'(K|G\d{1,2})\b').fillna('Unknown Grade')
                 melted_parity["Gender"] = melted_parity["GradeGender"].str.extract(r'(Male|Female)$').fillna('Unknown')

                 parity_data = melted_parity.groupby(["Grade", "Gender"], observed=False)["Count"].sum().reset_index()

                 all_possible_grades = ['K'] + [f'G{i}' for i in range(1, 13)]
                 parity_data['Grade'] = pd.Categorical(parity_data['Grade'], categories=all_possible_grades, ordered=True)
                 parity_data = parity_data.sort_values('Grade')

                 fig_grade_gender_parity = px.bar(
                     parity_data, x="Grade", y="Count", color="Gender", barmode="group",
                     title="Enrollment by Grade Level and Gender (Filtered)",
                     labels={'Count': 'Students', 'Grade': 'Grade Level', 'Gender': 'Gender'},
                     category_orders={"Grade": all_possible_grades},
                     template=PLOT_TEMPLATE, color_discrete_map=GENDER_COLORS
                 )
                 fig_grade_gender_parity.update_layout(title_font_size=14, legend_title_text='Gender', title_x=0.5, height=400, width=600) # Added height


        # 3. Sector Distribution Pie Chart - ADDED height=400
        fig_sector = create_placeholder_figure('Enrollment Distribution by Sector')
        if 'Sector' in filtered_df.columns and not filtered_df.empty and numeric_enrollment_cols_filtered:
             sector_enrollment = filtered_df.groupby("Sector")[numeric_enrollment_cols_filtered].sum().sum(axis=1).reset_index(name='Total Enrollment')
             sector_enrollment = sector_enrollment[(sector_enrollment['Total Enrollment'] > 0) & (sector_enrollment['Sector'] != 'Unknown')]
             if not sector_enrollment.empty:
                  fig_sector = px.pie(
                      sector_enrollment, names='Sector', values='Total Enrollment',
                      title='Enrollment Distribution by Sector (Filtered)',
                      hole=0.4, template=PLOT_TEMPLATE, color_discrete_sequence=QUALITATIVE_COLOR_SEQUENCE)
                  fig_sector.update_traces(textposition='outside', textinfo='percent+label', pull=[0.05]*len(sector_enrollment))
                  fig_sector.update_layout(title_font_size=14, legend_title_text='Sector', title_x=0.5, uniformtext_minsize=10, uniformtext_mode='hide', height=400, width=600) # Added height


        # 4. Education Stage Distribution Pie Chart - ADDED height=400
        fig_education_stage = create_placeholder_figure('Enrollment Distribution by Education Stage')
        if not filtered_df.empty and numeric_enrollment_cols_filtered:
             elem_cols = [col for col in numeric_enrollment_cols_filtered if any(col.startswith(g + ' ') for g in ['K'] + [f'G{i}' for i in range(1, 7)]) or 'Elem NG' in col]
             jhs_cols = [col for col in numeric_enrollment_cols_filtered if any(col.startswith(g + ' ') for g in [f'G{i}' for i in range(7, 11)]) or 'JHS NG' in col]
             shs_cols = [col for col in numeric_enrollment_cols_filtered if any(col.startswith(g + ' ') for g in ['G11', 'G12'])]

             elementary = filtered_df[elem_cols].sum().sum() if elem_cols else 0
             junior_high = filtered_df[jhs_cols].sum().sum() if jhs_cols else 0
             senior_high = filtered_df[shs_cols].sum().sum() if shs_cols else 0

             stage_data = pd.DataFrame({
                 'Stage': ['Elementary', 'Junior High School', 'Senior High School'],
                 'Enrollment': [elementary, junior_high, senior_high]
             })
             stage_data = stage_data[stage_data['Enrollment'] > 0]

             if not stage_data.empty:
                  fig_education_stage = px.pie(
                      stage_data, names='Stage', values='Enrollment',
                      title='Enrollment Distribution by Education Stage (Filtered)',
                      hole=0.4, template=PLOT_TEMPLATE, color_discrete_sequence=QUALITATIVE_COLOR_SEQUENCE)
                  fig_education_stage.update_traces(textposition='outside', textinfo='percent+label', pull=[0.05]*len(stage_data))
                  fig_education_stage.update_layout(title_font_size=14, legend_title_text='Stage', title_x=0.5, uniformtext_minsize=10, uniformtext_mode='hide', height=400, width=600) # Added height


        # --- Generate Detailed Analysis Figures ---

        # 5. SHS Specific Strand Enrollment by Gender (Combined Grouped Bar) - ADDED height=400
        fig_shs_strand_gender_combined = create_placeholder_figure('SHS Enrollment by Strand and Gender')
        shs_cols_numeric = [col for col in numeric_enrollment_cols_filtered if col.startswith('G11 ') or col.startswith('G12 ')]
        if shs_cols_numeric and not filtered_df.empty:
             strand_gender_data = []
             for col in shs_cols_numeric:
                 match = re.match(r'(G11|G12) (.*) (Male|Female)$', col)
                 if match:
                      grade, strand_name, gender = match.groups()
                      if strand_name.strip():
                          enrollment_sum = filtered_df[col].sum()
                          if enrollment_sum > 0:
                               strand_gender_data.append({'Grade': grade, 'Strand': strand_name.strip(), 'Gender': gender, 'Enrollment': enrollment_sum})

             if strand_gender_data:
                 strand_gender_df = pd.DataFrame(strand_gender_data)
                 strand_gender_agg = strand_gender_df.groupby(['Strand', 'Gender'], observed=False)['Enrollment'].sum().reset_index()

                 if not strand_gender_agg.empty:
                     fig_shs_strand_gender_combined = px.bar(
                         strand_gender_agg, x='Strand', y='Enrollment', color='Gender',
                         barmode='group', title='SHS Enrollment by Specific Strand/Track and Gender (Filtered)',
                         labels={'Enrollment': 'Students', 'Strand': 'Strand/Track', 'Gender': 'Gender'},
                         template=PLOT_TEMPLATE, color_discrete_map=GENDER_COLORS)
                     fig_shs_strand_gender_combined.update_layout(title_font_size=14, legend_title_text='Gender', title_x=0.5, height=400, width=600) # Added height
                     fig_shs_strand_gender_combined.update_xaxes(tickangle=30, categoryorder='total descending')


        # 6. Top 10 Most Populated Schools (Horizontal Bar) - ADDED height=400
        fig_top_schools = create_placeholder_figure('Top 10 Most Populated Schools')
        if 'BEIS School ID' in filtered_df.columns and 'School Name' in filtered_df.columns and not filtered_df.empty and numeric_enrollment_cols_filtered:
             enrollment_per_school = filtered_df.groupby(['BEIS School ID', 'School Name'])[numeric_enrollment_cols_filtered].sum().sum(axis=1).reset_index(name='Total Enrollment')
             top_schools = enrollment_per_school[enrollment_per_school['Total Enrollment'] > 0].nlargest(10, 'Total Enrollment')

             if not top_schools.empty:
                  top_schools['Display Name'] = top_schools.apply(lambda row: f"{row['School Name'][:40]}{'...' if len(row['School Name']) > 40 else ''} ({row['BEIS School ID']})", axis=1)

                  fig_top_schools = px.bar(
                      top_schools, y='Display Name', x='Total Enrollment', orientation='h',
                      title='Top 10 Most Populated Schools (Filtered)', text='Total Enrollment',
                      labels={'Total Enrollment': 'Total Enrollment', 'Display Name': 'School'},
                      template=PLOT_TEMPLATE, color='Total Enrollment',
                      color_continuous_scale=px.colors.sequential.Blues_r)
                  fig_top_schools.update_layout(title_font_size=14, yaxis={'categoryorder':'total ascending'}, title_x=0.5, height=400, width=600) # Added height
                  fig_top_schools.update_traces(textposition='outside')
                  fig_top_schools.update_coloraxes(showscale=False)


        # 7. Strand Enrollment Trend (G11 vs G12) (Line Chart) - ADDED height=400
        fig_strand_trend = create_placeholder_figure('SHS Strand Enrollment: G11 vs G12')
        # Use grade-filtered cols if G11/G12 selected, else base cols
        strand_trend_cols = numeric_enrollment_cols_filtered
        strand_trend_df_src = filtered_df
        if selected_grade not in ['G11', 'G12']:
             strand_trend_cols = all_numeric_enrollment_cols_in_base
             strand_trend_df_src = filtered_df_base_after_geo_sector_id

        g11_cols = [col for col in strand_trend_cols if col.startswith('G11 ')]
        g12_cols = [col for col in strand_trend_cols if col.startswith('G12 ')]

        if (g11_cols or g12_cols) and not strand_trend_df_src.empty:
            strand_trend_data = []
            strands = set()
            shs_pattern = re.compile(r'(G11|G12)\s+(.+)\s+(Male|Female)$')
            # Identify all unique strands present in G11/G12 columns
            for col in g11_cols + g12_cols:
                match = shs_pattern.match(col)
                if match:
                    strands.add(match.group(2).strip())

            # Calculate total G11 and G12 enrollment for each strand
            for strand in sorted(list(strands)):
                # Find all Male/Female columns for this strand in G11
                g11_strand_cols = [col for col in g11_cols if shs_pattern.match(col) and shs_pattern.match(col).group(2).strip() == strand]
                # Find all Male/Female columns for this strand in G12
                g12_strand_cols = [col for col in g12_cols if shs_pattern.match(col) and shs_pattern.match(col).group(2).strip() == strand]

                g11_total = strand_trend_df_src[g11_strand_cols].sum().sum() if g11_strand_cols else 0
                g12_total = strand_trend_df_src[g12_strand_cols].sum().sum() if g12_strand_cols else 0

                # Append data points only if enrollment exists
                if g11_total > 0 : strand_trend_data.append({'Strand': strand, 'Grade': 'G11', 'Enrollment': g11_total})
                if g12_total > 0 : strand_trend_data.append({'Strand': strand, 'Grade': 'G12', 'Enrollment': g12_total})

            if strand_trend_data:
                trend_df = pd.DataFrame(strand_trend_data)
                if not trend_df.empty:
                    fig_strand_trend = px.line(
                        trend_df, x='Strand', y='Enrollment', color='Grade', markers=True,
                        title='SHS Strand Enrollment: G11 vs G12',
                        labels={'Enrollment': 'Total Students', 'Strand': 'Strand/Track', 'Grade': 'Grade Level'},
                        template=PLOT_TEMPLATE,
                        color_discrete_map={'G11': '#1f77b4', 'G12': '#ff7f0e'} # Assign distinct colors
                    )
                    fig_strand_trend.update_layout(title_font_size=14, legend_title_text='Grade Level', title_x=0.5, height=400, width=600)
                    # Order strands alphabetically or by total enrollment if desired
                    fig_strand_trend.update_xaxes(tickangle=30, categoryorder='category ascending')


        # 9. Number of Schools Offering Each Strand (Treemap) - ADDED height=400
        fig_schools_offering_strand = create_placeholder_figure('Number of Schools Offering Each SHS Strand')
        shs_cols_base = [col for col in all_numeric_enrollment_cols_in_base if col.startswith('G11 ') or col.startswith('G12 ')]

        if shs_cols_base and 'BEIS School ID' in filtered_df_base_after_geo_sector_id.columns and not filtered_df_base_after_geo_sector_id.empty:
             schools_offering = {}
             for index, school in filtered_df_base_after_geo_sector_id.iterrows():
                 school_id = school['BEIS School ID']
                 if school_id == 'Unknown': continue
                 for col in shs_cols_base:
                      if col in school and school[col] > 0:
                          match = re.match(r'(G11|G12) (.*) (Male|Female)$', col)
                          if match:
                               strand_name = " ".join(match.groups()[1:-1])
                               if strand_name.strip():
                                    clean_strand_name = strand_name.strip()
                                    if clean_strand_name not in schools_offering:
                                        schools_offering[clean_strand_name] = set()
                                    schools_offering[clean_strand_name].add(school_id)

             if schools_offering:
                  strand_counts = [{'Strand': strand, 'Schools Offering': len(ids)} for strand, ids in schools_offering.items()]
                  strand_counts_df = pd.DataFrame(strand_counts).sort_values('Schools Offering', ascending=False)

                  if not strand_counts_df.empty:
                       fig_schools_offering_strand = px.treemap(
                           strand_counts_df, path=[px.Constant("All Strands"), 'Strand'], values='Schools Offering',
                           title='Number of Schools Offering Each SHS Strand/Track (Filtered Base)',
                           labels={'Schools Offering': 'Count of Schools', 'Strand': 'Strand/Track'},
                           template=PLOT_TEMPLATE, color='Schools Offering',
                           color_continuous_scale=px.colors.sequential.YlGnBu)
                       fig_schools_offering_strand.update_layout(title_font_size=14, title_x=0.5, height=400, width=600) # Added height
                       fig_schools_offering_strand.update_traces(textinfo="label+value")


        # --- Watchlist Table (Least Populated Schools) ---
        watchlist_table_component = html.P("No schools data available for watchlist based on current filters.", style={"fontSize": "0.9rem", "fontStyle": "italic", "textAlign": "center"})
        if 'BEIS School ID' in filtered_df.columns and 'School Name' in filtered_df.columns and not filtered_df.empty and numeric_enrollment_cols_filtered:
             enrollment_per_school_watchlist = filtered_df.groupby(['BEIS School ID', 'School Name'])[numeric_enrollment_cols_filtered].sum().sum(axis=1).reset_index(name='Filtered Total Enrollment')
             least_populated = enrollment_per_school_watchlist[enrollment_per_school_watchlist['Filtered Total Enrollment'] > 0].nsmallest(10, 'Filtered Total Enrollment')

             if not least_populated.empty:
                  cols_to_merge = ['BEIS School ID', 'Region', 'Division', 'Sector', 'School Type', 'School Subclassification']
                  cols_to_merge_present = [col for col in cols_to_merge if col in filtered_df.columns]

                  if cols_to_merge_present:
                       merge_info_df = filtered_df[cols_to_merge_present].drop_duplicates(subset=['BEIS School ID'])
                       least_populated = pd.merge(least_populated, merge_info_df, on='BEIS School ID', how='left')

                  table_cols_order = ['BEIS School ID', 'School Name', 'Filtered Total Enrollment', 'Sector', 'Division', 'Region', 'School Type', 'School Subclassification']
                  table_cols_final = [col for col in table_cols_order if col in least_populated.columns]

                  least_populated = least_populated[table_cols_final]

                  watchlist_table_component = dash_table.DataTable(
                      data=least_populated.to_dict("records"),
                      columns=[{"name": i.replace('Filtered Total Enrollment', 'Total Enrollment (Filtered)'), "id": i} for i in least_populated.columns],
                      page_size=10, style_table={'overflowX': 'auto'},
                      style_cell={'textAlign': 'left', 'fontSize': '0.8rem', 'padding': '5px', 'fontFamily': 'Arial, sans-serif', 'whiteSpace': 'normal', 'height': 'auto'},
                      style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f0f0'},
                      style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}],
                      sort_action="native",
                      filter_action="native",
                      id='watchlist-table'
                  )


        # --- Return all figures and components ---
        return (kpis, fig_region_bar, fig_grade_gender_parity, fig_sector, fig_education_stage,
                fig_shs_strand_gender_combined,
                fig_top_schools,
                fig_strand_trend,
                fig_schools_offering_strand,
                watchlist_table_component
               )

    @dash_app_report.callback(
        Output("download-data", "data"),
        Input("btn-download", "n_clicks"),
        State('region-filter', 'value'),
        State('division-filter', 'value'),
        State('grade-filter', 'value'),
        State('sector-filter', 'value'),
        State('beis-id-filter', 'value'),
        prevent_initial_call=True,
    )
    def download_filtered_data(n_clicks, selected_region, selected_division, selected_grade, selected_sector, selected_beis_id):
        filtered_df_download = df_all.copy()
        query_parts = []
        if selected_region and selected_region != 'Unknown': query_parts.append(f"Region == '{selected_region}'")
        if selected_division and selected_division != 'Unknown': query_parts.append(f"Division == '{selected_division}'")
        if selected_sector and selected_sector != 'Unknown': query_parts.append(f"Sector == '{selected_sector}'")
        if selected_beis_id and selected_beis_id != 'Unknown': query_parts.append(f"`BEIS School ID` == '{str(selected_beis_id)}'")

        if query_parts:
             filtered_df_download = filtered_df_download.query(" and ".join(query_parts)).copy()

        all_enrollment_cols = [
             col for col in df_all.columns
             if any(col.startswith(p) for p in ['K ', 'G1 ', 'G2 ', 'G3 ', 'G4 ', 'G5 ', 'G6 ', 'G7 ', 'G8 ', 'G9 ', 'G10 ', 'G11 ', 'G12 ', 'Elem NG ', 'JHS NG '])
             and (' Male' in col or ' Female' in col)
        ]
        non_enrollment_cols = [col for col in filtered_df_download.columns if col not in all_enrollment_cols]


        if selected_grade:
            grade_columns_to_keep_download = []
            for col in all_enrollment_cols:
                 if col in filtered_df_download.columns:
                     if col.startswith(selected_grade + " ") or (selected_grade == 'K' and col.startswith('K ')):
                         grade_columns_to_keep_download.append(col)

            columns_to_download = [col for col in non_enrollment_cols + grade_columns_to_keep_download if col in filtered_df_download.columns]
            filtered_df_to_download = filtered_df_download[columns_to_download]
        else:
            filtered_df_to_download = filtered_df_download

        csv_buffer = io.StringIO()
        filtered_df_to_download.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_buffer.seek(0)
        csv_data = csv_buffer.getvalue()

        return dict(content=csv_data, filename="filtered_enrollment_data.csv")

    return dash_app_report