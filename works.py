from flask import Flask, render_template_string
from dash import Dash, dcc, html, Input, Output, dash_table
import plotly.express as px
import pandas as pd
from data_config import get_dataset_path

# Flask server
server = Flask(__name__)

def create_dash_app(server, url_base_pathname='/dashenrollment/'):
    dash_app_works = Dash(
        __name__,
        server=server,
        url_base_pathname=url_base_pathname,
        external_stylesheets=[
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css",
            "https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap",
            "https://cdn.tailwindcss.com"
        ]
    )

    dash_app_works.layout = html.Div([
        html.Div([
            html.Div(id='summary-stats', className="w-3/4 mx-auto mb-6 p-4 bg-blue-100 rounded-md text-center font-semibold"),

            dcc.Dropdown(
                id='region-dropdown',
                placeholder="Select a region",
                className="w-3/4 mx-auto p-2 border border-gray-300 rounded-md shadow-sm"
            ),

            dcc.Dropdown(
                id='school-dropdown',
                placeholder="Select a school",
                className="w-3/4 mx-auto p-2 border border-gray-300 rounded-md shadow-sm mt-4"
            ),

            html.Div([
                dash_table.DataTable(
                    id='school-table',
                    columns=[{"name": col, "id": col} for col in ["School Name", "Region", "Province", "Municipality"]],
                    page_size=10,
                    filter_action="native",
                    sort_action="native",
                    style_table={'overflowX': 'auto', 'margin': '0 auto'},
                    style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '14px'},
                    style_header={'backgroundColor': '#333', 'color': 'white', 'fontWeight': 'bold'}
                ),
            ], className="w-3/4 mx-auto mt-6"),

            html.Div(className="flex w-3/4 mx-auto mt-6", children=[
                html.Div([dcc.Graph(id='enrollment-bar-chart')], className="w-1/2 pr-2"),
                html.Div(className="w-1/2 flex flex-col pl-2", children=[
                    html.Div([dcc.Graph(id='gender-pie-chart')], className="h-1/2 pb-2"),
                    html.Div([dcc.Graph(id='enrollment-line-chart')], className="h-1/2 pt-2")
                ])
            ]),

            html.Div(id='school-details', className="w-3/4 mx-auto mt-6 p-4 bg-white shadow-md rounded-md")
        ], className="max-w-3xl mx-auto bg-white p-6 shadow-lg rounded-md")
    ], className="bg-gray-100 min-h-screen flex items-center justify-center")

    @dash_app_works.callback(
        Output('region-dropdown', 'options'),
        Input('region-dropdown', 'id')  # dummy input
    )
    def populate_regions(_):
        df = pd.read_csv(get_dataset_path())
        return [{'label': region, 'value': region} for region in sorted(df['Region'].dropna().unique())]

    @dash_app_works.callback(
        Output('school-dropdown', 'options'),
        Input('region-dropdown', 'value')
    )
    def update_schools(region):
        df = pd.read_csv(get_dataset_path())
        filtered_df = df if not region else df[df['Region'] == region]
        return [{'label': school, 'value': school} for school in filtered_df['School Name'].unique()]

    @dash_app_works.callback(
        [Output('school-table', 'data'),
         Output('enrollment-bar-chart', 'figure'),
         Output('school-details', 'children'),
         Output('gender-pie-chart', 'figure'),
         Output('enrollment-line-chart', 'figure')],
        Input('school-dropdown', 'value')
    )
    def update_dashboard(selected_school):
        df = pd.read_csv(get_dataset_path())
        if not selected_school:
            empty_fig = px.bar(title='Select a school to view enrollment')
            return [], empty_fig, "", px.pie(title=''), px.line(title='')

        school_df = df[df['School Name'] == selected_school]
        table_data = school_df[["School Name", "Region", "Province", "Municipality"]].to_dict('records')

        grade_cols = [col for col in df.columns if col.startswith(('K ', 'G'))]
        enrollment_sums = school_df[grade_cols].sum()

        # Bar chart
        enrollment_fig = px.bar(
            x=enrollment_sums.index, y=enrollment_sums.values,
            labels={'x': 'Grade Level', 'y': 'Total Enrollment'},
            title=f'Total Student Enrollment for {selected_school}',
            color_discrete_sequence=['#3498db']
        )

        # Gender Pie Chart
        male_cols = [col for col in school_df.columns if 'male' in col.lower()]
        female_cols = [col for col in school_df.columns if 'female' in col.lower()]
        male_count = school_df[male_cols].sum().sum() if male_cols else 0
        female_count = school_df[female_cols].sum().sum() if female_cols else 0

        if male_count + female_count > 0:
            gender_fig = px.pie(
                values=[male_count, female_count],
                names=['Male', 'Female'],
                title='Gender Distribution',
                color_discrete_sequence=px.colors.sequential.RdBu
            )
        else:
            gender_fig = px.pie(title='No gender data available')

        # Line Chart
        line_fig = px.line(
            x=enrollment_sums.index, y=enrollment_sums.values,
            labels={'x': 'Grade Level', 'y': 'Enrollment'},
            title=f'Enrollment Trend for {selected_school}',
            markers=True
        )

        # School Details
        details = html.Div([
            html.H3(selected_school, className="text-xl font-bold"),
            html.P(f"Region: {school_df.iloc[0]['Region']}", className="text-gray-700"),
            html.P(f"Province: {school_df.iloc[0]['Province']}", className="text-gray-700"),
            html.P(f"Municipality: {school_df.iloc[0]['Municipality']}", className="text-gray-700"),
            html.P(f"Total Enrollment: {enrollment_sums.sum()}", className="text-gray-700 font-semibold")
        ])

        return table_data, enrollment_fig, details, gender_fig, line_fig

    @dash_app_works.callback(
        Output('summary-stats', 'children'),
        Input('region-dropdown', 'value')
    )
    def update_summary(region):
        df = pd.read_csv(get_dataset_path())
        if region:
            df = df[df['Region'] == region]
        total_schools = df['School Name'].nunique()
        grade_cols = [col for col in df.columns if col.startswith(('K ', 'G'))]
        avg_enrollment = df[grade_cols].sum(axis=1).mean()

        return f"Total Schools: {total_schools} | Average Enrollment: {int(avg_enrollment)}"

    return dash_app_works