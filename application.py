import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
import tempfile
import os

# Configure Gemini API key from secrets or environment
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
genai.configure(api_key=api_key)

# ---- Schema extraction ----
def extract_schema(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema_dict = {}
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        schema_dict[table_name] = columns
    return schema_dict

# ---- Gemini prompt ----
def get_sql_from_gemini(question, schema_text):
    prompt = f"""
You are a SQL expert. Generate a correct SQL query based on the user question and schema.

Schema:
{schema_text}

Question:
{question}

Important:
- Only return the SQL query (no explanation or markdown).
- Use only valid table and column names.
"""
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    response = model.generate_content(prompt)
    return response.text.strip().replace("```sql", "").replace("```", "").strip()

# ---- Streamlit App ----
st.set_page_config(page_title="Text-to-SQL (Gemini + SQLite)", layout="centered")
st.title("💬 Text-to-SQL Assistant")
st.markdown("Upload a `.db` SQLite file, ask a question, and Gemini will generate & run SQL.")

# ---- Upload ----
uploaded_file = st.file_uploader("📁 Upload SQLite Database", type=["db", "sqlite"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        schema_dict = extract_schema(conn)
        schema_text = "\n".join([f"{table}: {', '.join(cols)}" for table, cols in schema_dict.items()])

        # ---- Show schema UI ----
        with st.expander("📜 View Database Schema"):
            st.markdown("### 🗂️ Tables and Columns")
            for table, columns in schema_dict.items():
                st.markdown(f"**🔹 {table}**")
                st.table(pd.DataFrame(columns, columns=["Column Name"]))

        # ---- Ask question ----
        question = st.text_input("💡 Ask your question about the data:")

        if question:
            with st.spinner("🔍 Generating SQL with Gemini..."):
                try:
                    sql = get_sql_from_gemini(question, schema_text)
                    st.markdown("### 🧾 Generated SQL Query")
                    st.code(sql, language="sql")

                    df = pd.read_sql_query(sql, conn)
                    st.success("✅ Query executed successfully!")
                    st.dataframe(df)

                except Exception as e:
                    st.error(f"❌ Error: {e}")
        conn.close()

    except Exception as e:
        st.error(f"❌ Could not connect to database: {e}")
