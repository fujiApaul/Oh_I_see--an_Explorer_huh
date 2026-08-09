import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from collections import Counter
import json

st.set_page_config(
    page_title="ASEAN DSE Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


def clean_categories(text, category_type):
    """
    Cleans up AI cross-pollination where Tech Stacks were put in Solution Types and vice versa.
    It also standardizes spacing to prevent duplicate chart bars.
    """
    if pd.isna(text) or text == "Not Specified":
        return "Not Specified"

    # Split by comma and strip trailing/leading whitespaces
    items = [i.strip() for i in str(text).split(',')]
    cleaned_items = []

    for item in items:
        if category_type == 'tech':
            # Force Tech Stack standard formatting
            if item == 'Mobile/Web App':
                item = 'Mobile / Web App'
            elif item == 'Hardware/IoT Device':
                item = 'IoT / Smart Sensors'
        elif category_type == 'solution':
            # Force Solution standard formatting
            if item == 'Mobile / Web App':
                item = 'Mobile/Web App'
            elif item == 'IoT / Smart Sensors':
                item = 'Hardware/IoT Device'

        cleaned_items.append(item)

    # Convert to set and back to list to remove any duplicates created by the merge, then join
    return ", ".join(list(set(cleaned_items)))


def get_top_buzzwords(df_subset, column_name, top_n=10):
    """
    Extracts the most common meaningful words from a text column.
    """
    if df_subset.empty:
        return pd.DataFrame(columns=['Word', 'Count'])

    # A basic set of stop words to filter out
    stop_words = set(
        ['the', 'and', 'to', 'of', 'a', 'in', 'for', 'is', 'on', 'that', 'by', 'this', 'with', 'i', 'you', 'it', 'not',
         'or', 'be', 'are', 'from', 'at', 'as', 'your', 'all', 'have', 'new', 'more', 'an', 'was', 'we', 'will', 'home',
         'can', 'us', 'about', 'if', 'page', 'my', 'has', 'no', 'our', 'do', 'they', 'their', 'which', 'up', 'out',
         'them', 'through', 'an', 'its', 'into'])

    text = " ".join(df_subset[column_name].dropna().astype(str)).lower()
    # Find all words with 4 or more characters
    words = re.findall(r'\b[a-z]{4,}\b', text)
    meaningful_words = [w for w in words if w not in stop_words]

    counts = Counter(meaningful_words).most_common(top_n)
    return pd.DataFrame(counts, columns=['Word', 'Count'])


@st.cache_data
def load_data():
    """Loads the CSV data and handles potential filename variations."""
    filenames = ["asean_dse_data.csv", "asean_dse_data - asean_dse_data.csv.csv"]
    df = None

    for file in filenames:
        if os.path.exists(file):
            df = pd.read_csv(file)
            break

    if df is None:
        st.error(
            "⚠️ Could not find the CSV file. Please ensure 'asean_dse_data.csv' is in the same folder as this script.")
        st.stop()

    # Clean up any NA values for clean charting
    df.fillna("Not Specified", inplace=True)

    # Apply the AI cleanup function
    df['Tech Stack Integrated'] = df['Tech Stack Integrated'].apply(lambda x: clean_categories(x, 'tech'))
    df['Solution Type'] = df['Solution Type'].apply(lambda x: clean_categories(x, 'solution'))

    # Calculate the SDG Complexity Index (How many SDGs did they target?)
    df['SDG Count'] = df['Target SDGs'].apply(
        lambda x: len(str(x).split(',')) if x != "Not Specified" and pd.notna(x) else 0
    )

    return df


def explode_column(df, column_name):
    """
    Helper function to split comma-separated strings into individual rows.
    """
    temp_df = df.copy()
    temp_df[column_name] = temp_df[column_name].astype(str).str.split(r',\s*')
    return temp_df.explode(column_name)


def get_stats_dict(data_subset):
    """Creates a standardized dictionary of stats for JSON export."""
    if data_subset.empty:
        return {}

    sdg_counts = explode_column(data_subset, 'Target SDGs')['Target SDGs'].value_counts().to_dict()
    tech_counts = explode_column(data_subset, 'Tech Stack Integrated')['Tech Stack Integrated'].value_counts().to_dict()
    sol_counts = explode_column(data_subset, 'Solution Type')['Solution Type'].value_counts().to_dict()
    ben_counts = data_subset['Target Beneficiary'].value_counts().to_dict()
    comp_counts = {f"{int(k)} SDGs": v for k, v in data_subset['SDG Count'].value_counts().items()}

    team_mapping = {True: 'Different Universities', False: 'Same University', "TRUE": 'Different Universities',
                    "FALSE": 'Same University', "True": 'Different Universities', "False": 'Same University'}
    if 'Cross-Institution Team' in data_subset.columns:
        team_counts = data_subset['Cross-Institution Team'].map(team_mapping).fillna('Unknown').value_counts().to_dict()
    else:
        team_counts = {}

    buzz_df = get_top_buzzwords(data_subset, 'Brief Description', top_n=10)
    buzz_dict = dict(zip(buzz_df['Word'], buzz_df['Count'])) if not buzz_df.empty else {}

    return {
        "total_storyboards": len(data_subset),
        "sdg_distribution": sdg_counts,
        "beneficiary_distribution": ben_counts,
        "tech_stack_distribution": tech_counts,
        "solution_type_distribution": sol_counts,
        "sdg_complexity_distribution": comp_counts,
        "team_formation_distribution": team_counts,
        "top_buzzwords": buzz_dict
    }


def generate_export_report(filtered_df, df, year, country, beneficiary):
    """Generates a clean Markdown report string containing both Overall and Winners metrics."""
    if filtered_df.empty:
        return "# 📊 ASEAN DSE Analytics Summary Report\nNo data available for the current filters."

    current_winners = filtered_df[filtered_df['Rank Placement'].isin(['1st Place', '2nd Place', '3rd Place'])]
    winners_hall_of_fame = df[df['Rank Placement'].isin(['1st Place', '2nd Place', '3rd Place'])]

    def create_markdown_section(data_subset, title):
        if data_subset.empty:
            return f"## {title}\n*No data available for this subset.*\n"

        stats = get_stats_dict(data_subset)

        # Determine Top Items safely
        top_sdg = list(stats['sdg_distribution'].keys())[0] if stats['sdg_distribution'] else "N/A"
        top_tech = list(stats['tech_stack_distribution'].keys())[0] if stats['tech_stack_distribution'] else "N/A"
        top_sol = list(stats['solution_type_distribution'].keys())[0] if stats['solution_type_distribution'] else "N/A"

        return f"""## {title}
**Total Storyboards Analyzed:** {stats['total_storyboards']}
**Top Targeted SDG:** {top_sdg} | **Top Tech Stack:** {top_tech} | **Top Solution Type:** {top_sol}

### 🎯 Target SDGs Breakdown
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['sdg_distribution'].items()])}

### 👥 Primary Beneficiaries Breakdown
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['beneficiary_distribution'].items()])}

### 🛠️ Preferred Tech Stacks Breakdown
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['tech_stack_distribution'].items()])}

### 📱 Solution Types Breakdown
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['solution_type_distribution'].items()])}

### 🧩 SDG Complexity (Number of SDGs Targeted)
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['sdg_complexity_distribution'].items()])}

### 🤝 Team Formation
{chr(10).join([f'- **{k}**: {v} team(s)' for k, v in stats['team_formation_distribution'].items()])}

### 🗣️ Top 10 Buzzwords Used
{chr(10).join([f'- **"{k}"**: {v} times' for k, v in stats['top_buzzwords'].items()]) if stats['top_buzzwords'] else "No buzzwords extracted."}
"""

    report = f"""# 📊 ASEAN DSE Analytics Summary Report
**Generated Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}

---

## 🔍 Active Filters Applied
- **Selected Year:** {year}
- **Selected Country:** {country}
- **Selected Beneficiary:** {beneficiary}
- **Total Unique Countries Represented:** {filtered_df['Country'].nunique()}

---

{create_markdown_section(filtered_df, "🌐 OVERALL REGIONAL TRENDS")}

---

{create_markdown_section(current_winners, "🥇 THE WINNERS' PLAYBOOK (1st, 2nd, 3rd Place)")}

---

## 🏆 Podium Finishes by Country (All-Time Hall of Fame)
{chr(10).join([f'- **{k}**: {v} podium finish(es)' for k, v in winners_hall_of_fame['Country'].value_counts().items()])}

---
*Report generated automatically from ASEAN DSE Analytics Dashboard.*
"""
    return report


df = load_data()

st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/8/87/ASEAN_Emblem.svg/250px-ASEAN_Emblem.svg.png",
                 width=150)
st.sidebar.title("Data Filters")

# Filter 1: Year
all_years = ["All Time"] + sorted(list(df['Year'].unique()), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", all_years)

# Filter 2: Country
all_countries = ["All Countries"] + sorted(list(df['Country'].unique()))
selected_country = st.sidebar.selectbox("Select Country", all_countries)

# Filter 3: Beneficiary
all_beneficiaries = ["All Beneficiaries"] + sorted(
    list(explode_column(df, 'Target Beneficiary')['Target Beneficiary'].unique()))
selected_beneficiary = st.sidebar.selectbox("Select Target Beneficiary", all_beneficiaries)

filtered_df = df.copy()
if selected_year != "All Time":
    filtered_df = filtered_df[filtered_df['Year'] == selected_year]
if selected_country != "All Countries":
    filtered_df = filtered_df[filtered_df['Country'] == selected_country]
if selected_beneficiary != "All Beneficiaries":
    filtered_df = filtered_df[filtered_df['Target Beneficiary'].str.contains(selected_beneficiary, na=False)]

st.sidebar.markdown("---")
st.sidebar.header("📥 Export Center")

if not filtered_df.empty:
    # 1. Export Filtered Dataset (CSV)
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📄 Download Filtered CSV",
        data=csv_data,
        file_name=f"asean_dse_filtered_{selected_year}_{selected_country}.csv",
        mime="text/csv",
        help="Download the underlying raw dataset matching your active sidebar filters."
    )

    # 2. Export Summary Executive Report (Markdown)
    markdown_report = generate_export_report(
        filtered_df, df, selected_year, selected_country, selected_beneficiary
    )
    st.sidebar.download_button(
        label="📝 Download Summary Report (.md)",
        data=markdown_report,
        file_name=f"ASEAN_DSE_Executive_Summary_{selected_year}.md",
        mime="text/markdown",
        help="Download a formatted Markdown report summarizing all key charts and metrics."
    )

    # 3. Export Key Statistics (JSON)
    current_winners = filtered_df[filtered_df['Rank Placement'].isin(['1st Place', '2nd Place', '3rd Place'])]

    json_stats = {
        "metadata": {
            "filter_year": selected_year,
            "filter_country": selected_country,
            "filter_beneficiary": selected_beneficiary
        },
        "overall_stats": get_stats_dict(filtered_df),
        "winners_playbook_stats": get_stats_dict(current_winners)
    }

    st.sidebar.download_button(
        label="📊 Download Summary Stats (.json)",
        data=json.dumps(json_stats, indent=4),
        file_name=f"asean_dse_stats_{selected_year}.json",
        mime="application/json",
        help="Download structured JSON statistics (including Winners deltas) for programmatic analysis."
    )

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Pro Tip for Participants:**\n\n"
    "Switch between the 'Overall' and 'Winners' tabs. Look for the deltas. "
    "Do winners tackle more SDGs at once than average teams? Which buzzwords do they use in their pitches?"
)

st.title("📊 ASEAN Data Science Explorers: Master Analytics")
st.markdown("Unlock strategic insights from past Regional Finalists to build a winning storyboard.")

if filtered_df.empty:
    st.warning("No storyboards match your current filter selection. Please adjust your filters.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Storyboards Analyzed", value=len(filtered_df))
with col2:
    st.metric(label="Unique Countries Represented", value=filtered_df['Country'].nunique())
with col3:
    sdg_df_overall = explode_column(filtered_df, 'Target SDGs')
    top_sdg = sdg_df_overall['Target SDGs'].mode()[0] if not sdg_df_overall.empty else "N/A"
    st.metric(label="Most Targeted SDG", value=top_sdg)
with col4:
    sol_df_overall = explode_column(filtered_df, 'Solution Type')
    top_sol = sol_df_overall['Solution Type'].mode()[0] if not sol_df_overall.empty else "N/A"
    st.metric(label="Most Popular Solution", value=top_sol)

st.markdown("---")

r0c1, r0c2 = st.columns([1, 1])

with r0c1:
    st.header("🏆 The Hall of Fame")
    st.write("Countries with the most 1st, 2nd, or 3rd place finishes.")
    winners_df = df[df['Rank Placement'].isin(['1st Place', '2nd Place', '3rd Place'])]
    winner_counts = winners_df['Country'].value_counts().reset_index()
    winner_counts.columns = ['Country', 'Number of Podiums']

    fig_winners = px.bar(
        winner_counts, x='Country', y='Number of Podiums', color='Number of Podiums',
        color_continuous_scale='YlGnBu', text_auto=True
    )
    fig_winners.update_layout(xaxis_title="", yaxis_title="Top 3 Placements", template="plotly_white")
    st.plotly_chart(fig_winners, use_container_width=True)

with r0c2:
    st.header("📈 The Tech Evolution")
    st.write("How technology adoption has shifted over time.")
    tech_over_time = explode_column(df, 'Tech Stack Integrated')
    # Group by year and tech stack, then count
    tech_trend = tech_over_time.groupby(['Year', 'Tech Stack Integrated']).size().reset_index(name='Count')

    fig_trend = px.line(
        tech_trend, x='Year', y='Count', color='Tech Stack Integrated', markers=True,
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig_trend.update_layout(xaxis_title="", yaxis_title="Number of Teams", template="plotly_white", legend_title="")
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")


def render_charts(data_subset, title, color_theme_bar, color_theme_pie):
    """
    A reusable function to generate the exact same charts for easy comparison.
    """
    st.header(title)

    if data_subset.empty:
        st.warning("No data available for this subset.")
        return

    # Pre-explode data for this subset
    sub_sdg_df = explode_column(data_subset, 'Target SDGs')
    sub_tech_df = explode_column(data_subset, 'Tech Stack Integrated')
    sub_sol_df = explode_column(data_subset, 'Solution Type')

    # Row 1: SDGs and Beneficiaries
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.subheader("🎯 Most Targeted SDGs")
        sdg_counts = sub_sdg_df['Target SDGs'].value_counts().reset_index()
        sdg_counts.columns = ['SDG', 'Count']
        fig_sdg = px.bar(
            sdg_counts.head(10), y='SDG', x='Count', orientation='h',
            color='Count', color_continuous_scale=color_theme_bar
        )
        fig_sdg.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white")
        st.plotly_chart(fig_sdg, use_container_width=True)

    with r1c2:
        st.subheader("👥 Primary Beneficiaries")
        ben_counts = data_subset['Target Beneficiary'].value_counts().reset_index()
        ben_counts.columns = ['Beneficiary', 'Count']
        fig_ben = px.pie(
            ben_counts, values='Count', names='Beneficiary', hole=0.4,
            color_discrete_sequence=color_theme_pie
        )
        st.plotly_chart(fig_ben, use_container_width=True)

    # Row 2: Tech Stacks and Solution Types
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.subheader("🛠️ Preferred Tech Stacks")
        tech_counts = sub_tech_df['Tech Stack Integrated'].value_counts().reset_index()
        tech_counts.columns = ['Technology', 'Count']
        fig_tech = px.bar(
            tech_counts, x='Technology', y='Count', color='Count',
            color_continuous_scale=color_theme_bar, text_auto=True
        )
        fig_tech.update_layout(template="plotly_white", xaxis_title="")
        st.plotly_chart(fig_tech, use_container_width=True)

    with r2c2:
        st.subheader("📱 Types of Solutions")
        sol_counts = sub_sol_df['Solution Type'].value_counts().reset_index()
        sol_counts.columns = ['Solution Type', 'Count']
        fig_sol = px.bar(
            sol_counts, y='Solution Type', x='Count', orientation='h',
            color='Count', color_continuous_scale=color_theme_bar
        )
        fig_sol.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white")
        st.plotly_chart(fig_sol, use_container_width=True)

    # Row 3: The New Strategic Indicators (Complexity, Team, Buzzwords)
    r3c1, r3c2, r3c3 = st.columns(3)
    with r3c1:
        st.subheader("🧩 SDG Complexity")
        st.caption("How many SDGs do they target?")
        comp_counts = data_subset['SDG Count'].value_counts().reset_index()
        comp_counts.columns = ['Number of SDGs', 'Count']
        comp_counts['Number of SDGs'] = comp_counts['Number of SDGs'].astype(str) + " SDGs"
        fig_comp = px.bar(
            comp_counts, x='Number of SDGs', y='Count', color='Count',
            color_continuous_scale=color_theme_bar, text_auto=True
        )
        fig_comp.update_layout(xaxis={'categoryorder': 'category ascending'}, template="plotly_white", xaxis_title="",
                               yaxis_title="")
        st.plotly_chart(fig_comp, use_container_width=True)

    with r3c2:
        st.subheader("🤝 Team Formation")
        st.caption("Different Universities?")
        if 'Cross-Institution Team' in data_subset.columns:
            team_counts = data_subset['Cross-Institution Team'].value_counts().reset_index()
            team_counts.columns = ['Cross-Institution', 'Count']
            mapping = {True: 'Different Universities', False: 'Same University', "TRUE": 'Different Universities',
                       "FALSE": 'Same University', "True": 'Different Universities', "False": 'Same University'}
            team_counts['Cross-Institution'] = team_counts['Cross-Institution'].map(mapping).fillna('Unknown')
            fig_team = px.pie(
                team_counts, values='Count', names='Cross-Institution', hole=0.4,
                color_discrete_sequence=color_theme_pie
            )
            fig_team.update_layout(showlegend=False)
            st.plotly_chart(fig_team, use_container_width=True)

    with r3c3:
        st.subheader("🗣️ Top Buzzwords")
        st.caption("Most used words in descriptions.")
        buzz_df = get_top_buzzwords(data_subset, 'Brief Description', top_n=8)
        if not buzz_df.empty:
            fig_buzz = px.bar(
                buzz_df, y='Word', x='Count', orientation='h', color='Count',
                color_continuous_scale=color_theme_bar
            )
            fig_buzz.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white", xaxis_title="",
                                   yaxis_title="")
            st.plotly_chart(fig_buzz, use_container_width=True)


tab1, tab2 = st.tabs(["🌐 Overall Regional Trends", "🥇 The Winners' Playbook"])

with tab1:
    render_charts(filtered_df, "🌐 Overall Regional Trends", 'Purples', px.colors.qualitative.Pastel)

with tab2:
    if not current_winners.empty:
        render_charts(current_winners, "🥇 The Winners' Playbook (1st, 2nd, 3rd Place)", 'Greens',
                      px.colors.qualitative.Set2)
    else:
        st.warning("No podium winners found for the currently selected filters.")

st.markdown("---")
st.header("🧠 Strategic Insights for Future Participants")

st.info(
    """
    **How to use this data to win:**

    1. **Check the Momentum:** Look at the *Tech Evolution* chart. AI/Machine Learning and IoT are on a massive upward trajectory. A dashboard alone isn't enough anymore; integrating predictive AI or hardware sensors gives you a massive competitive edge.
    2. **Check the Complexity (The Delta):** Look at the *SDG Complexity Index* in both tabs. If average teams target 1-2 SDGs, but Winners target 3-4, you know the judges reward highly interlinked, systemic solutions.
    3. **The "Blue Ocean" Strategy:** Look at the *least* targeted SDGs and Beneficiaries using the sidebar filters. If 80% of teams are building Mobile Apps for Urban Populations, that space is crowded. Building a Hardware/IoT solution for Rural Fishermen automatically makes your storyboard unique to the judges.
    4. **Speak their Language:** Check the *Top Buzzwords* in the Winners tab. Incorporating words like "sustainable", "circular", "platform", and "framework" into your pitch shows you understand the macroscopic goals of the ASEAN community.
    """
)

st.markdown("---")
with st.expander("🔍 Explore the Raw Data"):
    st.dataframe(filtered_df[['Year', 'Country', 'Rank Placement', 'Team Name', 'Storyboard Title', 'Target SDGs',
                              'Target Beneficiary',
                              'Tech Stack Integrated', 'Cross-Institution Team']])