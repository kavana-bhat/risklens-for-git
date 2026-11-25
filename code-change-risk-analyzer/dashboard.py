import streamlit as st
import pandas as pd


# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Code Change Risk Analyzer",
    page_icon="🛡️",
    layout="wide"
)


# ==========================================
# LOAD DATA
# ==========================================

try:
    data = pd.read_csv("risk_history.csv")

except FileNotFoundError:
    st.error("risk_history.csv not found.")
    st.stop()


if data.empty:
    st.warning("No analysis history available.")
    st.stop()


# ==========================================
# TITLE
# ==========================================

st.title("🛡️ Code Change Risk Analyzer")

st.write(
    "AI-powered Git change analysis using "
    "dependency analysis, impact analysis, "
    "automated testing and machine learning."
)


st.divider()


# ==========================================
# BASIC STATISTICS
# ==========================================

total = len(data)

high = len(
    data[data["risk"] == "HIGH"]
)

medium = len(
    data[data["risk"] == "MEDIUM"]
)

low = len(
    data[data["risk"] == "LOW"]
)

average_confidence = data[
    "confidence"
].mean()

total_files = data[
    "files_changed"
].sum()

total_functions = data[
    "functions_changed"
].sum()


# ==========================================
# TOP METRICS
# ==========================================

col1, col2, col3, col4 = st.columns(4)


with col1:
    st.metric(
        "Total Analyses",
        total
    )


with col2:
    st.metric(
        "🔴 High Risk",
        high
    )


with col3:
    st.metric(
        "🟠 Medium Risk",
        medium
    )


with col4:
    st.metric(
        "🟢 Low Risk",
        low
    )


# ==========================================
# SECONDARY METRICS
# ==========================================

st.subheader("Project Statistics")


col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "Average ML Confidence",
        f"{average_confidence:.2f}%"
    )


with col2:
    st.metric(
        "Files Analyzed",
        int(total_files)
    )


with col3:
    st.metric(
        "Functions Analyzed",
        int(total_functions)
    )


# ==========================================
# TEST GAP OVERVIEW  (NEW)
# ==========================================

if "untested_blast" in data.columns:

    gap_data = data.copy()

    for column in ["blast_radius", "untested_blast", "untested_changed"]:
        gap_data[column] = pd.to_numeric(
            gap_data[column],
            errors="coerce"
        )

    gap_data = gap_data.dropna(subset=["untested_blast"])

    if not gap_data.empty:

        st.subheader("Test Gap Overview")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Avg blast radius (functions)",
                f"{gap_data['blast_radius'].mean():.1f}"
            )

        with col2:
            st.metric(
                "Untested functions (total)",
                int(gap_data["untested_blast"].sum())
            )

        with col3:
            with_gap = int(
                (gap_data["untested_changed"] > 0).sum()
            )
            st.metric(
                "Analyses with changed code untested",
                f"{with_gap} / {len(gap_data)}"
            )

        chart = gap_data.copy()
        chart.index = chart["commit_id"].astype(str)

        st.bar_chart(
            chart[["blast_radius", "untested_blast"]]
        )

        st.caption(
            "Blast radius = changed functions + everything that calls them. "
            "Untested = no test can reach it through the call graph."
        )

# ==========================================
# RISK DISTRIBUTION
# ==========================================

st.subheader("Risk Distribution")


risk_counts = (
    data["risk"]
    .value_counts()
)

st.bar_chart(
    risk_counts
)


# ==========================================
# RISK TREND
# ==========================================

st.subheader("Risk Analysis History")


risk_mapping = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3
}


trend = data.copy()

trend["risk_score"] = trend[
    "risk"
].map(
    risk_mapping
)

trend.index = range(
    1,
    len(trend) + 1
)


st.line_chart(
    trend["risk_score"]
)


st.caption(
    "Risk score: LOW = 1, MEDIUM = 2, HIGH = 3"
)


# ==========================================
# ANALYSIS TABLE
# ==========================================

st.subheader("Analysis History")


columns = [

    "timestamp",

    "commit_id",

    "commit_message",

    "files_changed",

    "insertions",

    "deletions",

    "affected_files",

    "functions_changed",

    "test_failures",

    "risk",

    "confidence",

    "blast_radius",

    "untested_blast",

    "untested_changed"

]


available_columns = [

    column

    for column in columns

    if column in data.columns

]


st.dataframe(
    data[available_columns],
    use_container_width=True
)


# ==========================================
# RISK FILTER
# ==========================================

st.subheader("Filter Analysis")


selected_risk = st.selectbox(

    "Risk Level",

    [
        "ALL",
        "HIGH",
        "MEDIUM",
        "LOW"
    ]

)


if selected_risk == "ALL":

    filtered = data

else:

    filtered = data[
        data["risk"] == selected_risk
    ]


st.dataframe(
    filtered[available_columns],
    use_container_width=True
)


# ==========================================
# LATEST ANALYSIS
# ==========================================

st.subheader("Latest Analysis")


latest = data.iloc[-1]


col1, col2 = st.columns(2)


with col1:

    st.write(
        "**Commit:**",
        latest["commit_id"]
    )

    st.write(
        "**Message:**",
        latest["commit_message"]
    )

    st.write(
        "**Risk Level:**",
        latest["risk"]
    )


with col2:

    st.write(
        "**Files Changed:**",
        latest["files_changed"]
    )

    st.write(
        "**Affected Files:**",
        latest["affected_files"]
    )

    st.write(
        "**ML Confidence:**",
        f"{latest['confidence']}%"
    )


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "Code Change Risk Analyzer | "
    "Git + Dependency Graph + Impact Analysis + "
    "Automated Testing + Machine Learning"
)