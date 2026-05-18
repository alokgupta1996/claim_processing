FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY src /app/src
COPY *.xlsx /app/
COPY Assignment_Brief.docx /app/
COPY Sample_Claims_Analysis_Report.pdf /app/
COPY pytest.ini /app/pytest.ini

RUN mkdir -p /app/data/processed /app/outputs /app/configs/mappings

EXPOSE 8501 8502

CMD ["python", "-m", "streamlit", "run", "src/ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
