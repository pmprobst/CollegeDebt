# CollegeDebt

## Streamlit app

**Major Explorer** uses the most recent field-of-study file; **Trends Over Time** loads the eight pooled award-year panel CSVs (`FieldOfStudyData*_PP_slim.csv`) under `Data/IPEDS_College_Scorecard/FieldOfStudy/`.

Use a virtual environment so dependencies stay isolated.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Deactivate when done: `deactivate`.
