import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import seaborn as sns

# ========= 1. Functions for cleaning ==========

def clean_data(text):
    if not text:
        return "N/A"
    text = text.strip()
    start, end = 0, len(text) - 1
    while start < len(text) and not text[start].isalpha():
        start += 1
    while end >= 0 and not text[end].isalpha():
        end -= 1
    return text[start:end+1] if start <= end else "N/A"

def extract_city(location_series):
    cities = []
    for loc in location_series:
        if pd.isna(loc):
            cities.append("N/A")
        elif ',' in loc:
            parts = loc.split(',')
            city = parts[-2].strip() if len(parts) > 1 else "N/A"
            cities.append(city)
        else:
            cities.append("N/A")
    return cities

def extract_country(location_series):
    countries = []
    updated_locations = []
    for loc in location_series:
        if pd.isna(loc):
            countries.append("N/A")
            updated_locations.append("N/A")
        elif ',' in loc:
            parts = loc.split(',')
            country = parts[-1].strip()
            location_without_country = ', '.join(parts[:-1]).strip()
            countries.append(country)
            updated_locations.append(location_without_country)
        else:
            countries.append("N/A")
            updated_locations.append(loc)
    return updated_locations, countries

job_type_keywords = ['Full Time', 'Part Time', 'Freelance', 'Remote', 'On-site', 'Hybrid', 'Internship', 'Shift Based']

def clean_skills(text):
    if pd.isna(text):
        return "N/A"
    parts = [part.strip() for part in text.split(',')]
    filtered_parts = [part for part in parts if part not in job_type_keywords]
    return ', '.join(filtered_parts) if filtered_parts else "N/A"

def clean_and_deduplicate_skills(text):
    if pd.isna(text):
        return "N/A"
    skills = [s.strip() for s in text.split(',')]
    unique_skills = list(dict.fromkeys(skills))
    return ', '.join(unique_skills) if unique_skills else "N/A"

# ========= 2. Load and preprocess data ==========

@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df.columns = (
        df.columns
          .astype(str)
          .str.strip()
          .str.lower()
          .str.replace(' ', '_', regex=False)
    )

    # Cleaning operations
    if 'location' in df.columns:
        df['location'] = df['location'].apply(clean_data)
        df['city'] = extract_city(df['location'])
        df['location'], df['country'] = extract_country(df['location'])
    else:
        df['city'] = ["N/A"] * len(df)
        df['country'] = ["N/A"] * len(df)

    if 'skills' in df.columns:
        df['skills'] = df['skills'].apply(clean_skills)
        df['skills'] = df['skills'].apply(clean_and_deduplicate_skills)
        df['skills_list'] = (
            df['skills']
              .fillna('')
              .astype(str)
              .str.split(r',\s*')
        )
    else:
        df['skills_list'] = [[] for _ in range(len(df))]

    # Drop unnecessary columns if they exist
    df = df.drop(columns=[col for col in ['salary', 'location'] if col in df.columns])

    # Remove duplicate jobs
    df = df.drop_duplicates(subset=['job_title', 'company'])

    return df

# ========= 3. Main App ==========

def main():
    global df

    st.set_page_config(page_title="Wuzzuf Jobs Dashboard", layout="wide")
    st.title("Wuzzuf Jobs Analysis")

    # Sidebar: Upload or path input
    st.sidebar.header("بيانات المشروع")
    uploaded_file = st.sidebar.file_uploader("ارفع ملف Excel النهائي", type=["xlsx"])
    if uploaded_file is not None:
        df = load_data(uploaded_file)
    else:
        data_file = st.sidebar.text_input(
            "أو أدخل مسار ملف البيانات", 
            r"D:\data tools project\wuzzuf_jobs_20250428_074738.xlsx"
        )
        if data_file:
            df = load_data(data_file)
        else:
            st.warning("يرجى رفع ملف Excel أو تحديد مسار الملف.")
            st.stop()
            # Sidebar filters
    st.sidebar.header("التصفية")
    cities = st.sidebar.multiselect(
        "اختيار المدن:", options=sorted(df['city'].dropna().unique())
    )
    companies = st.sidebar.multiselect(
        "اختيار الشركات:", options=sorted(df['company'].dropna().unique())
    )
    job_types = []
    if 'job_type' in df.columns:
        job_types = st.sidebar.multiselect(
            "اختيار نوع الوظيفة:", options=sorted(df['job_type'].dropna().unique())
        )

    # Apply filters
    filtered_df = df.copy()
    if cities:
        filtered_df = filtered_df[filtered_df['city'].isin(cities)]
    if companies:
        filtered_df = filtered_df[filtered_df['company'].isin(companies)]
    if job_types and 'job_type' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['job_type'].isin(job_types)]

    # KPI metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي الوظائف", len(filtered_df))
    col2.metric("شركات فريدة", filtered_df['company'].nunique() if 'company' in filtered_df.columns else 0)
    col3.metric("مهارات فريدة", len({skill for lst in filtered_df['skills_list'] for skill in lst}))

    # Top Skills Bar Chart
    all_skills = [skill for sub in filtered_df['skills_list'] for skill in sub]
    if all_skills:
        skills_count = pd.Series(all_skills).value_counts().head(10)
        fig1, ax1 = plt.subplots()
        ax1.barh(skills_count.index[::-1], skills_count.values[::-1])
        ax1.set_title("أكثر 10 مهارات مطلوبة")
        ax1.set_xlabel("عدد الوظائف")
        st.pyplot(fig1)

    # Top Cities Bar Chart
    if 'city' in filtered_df.columns:
        city_count = filtered_df['city'].value_counts().head(10)
        fig2, ax2 = plt.subplots()
        sns.barplot(x=city_count.values, y=city_count.index, ax=ax2)
        ax2.set_title("أفضل المدن للوظائف")
        ax2.set_xlabel("عدد الوظائف")
        st.pyplot(fig2)

    # Word Cloud for Job Titles
    if st.sidebar.checkbox("عرض Word Cloud للعناوين الوظيفية"):
        if 'job_title' in filtered_df.columns:
            titles = filtered_df['job_title'].dropna().astype(str)
            text = ' '.join(titles)
            wc = WordCloud(width=800, height=400, background_color='white').generate(text)
            fig3, ax3 = plt.subplots(figsize=(10, 5))
            ax3.imshow(wc, interpolation='bilinear')
            ax3.axis('off')
            st.pyplot(fig3)

    # Top Companies Bar Chart
    if 'company' in filtered_df.columns:
        comp_count = filtered_df['company'].value_counts().head(10)
        fig4, ax4 = plt.subplots()
        sns.barplot(x=comp_count.values, y=comp_count.index, ax=ax4)
        ax4.set_title("أعلى الشركات توظيفًا")
        ax4.set_xlabel("عدد الوظائف")
        st.pyplot(fig4)

# ========= 4. Run App ==========

if __name__ == "__main__":
    main()