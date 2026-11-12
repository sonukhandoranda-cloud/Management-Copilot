
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

# Run from NoteBooks because the database paths are relative
WORKDIR /app/NoteBooks

EXPOSE 8501

CMD ["streamlit", "run", "../app.py", "--server.address=0.0.0.0"]
