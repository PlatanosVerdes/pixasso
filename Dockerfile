FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd -M -u 10001 pixasso \
    && install -d -o pixasso -g pixasso -m 700 /data
COPY pixasso/ ./pixasso/

# The TV pairing token lives here; without the mount every redeploy asks "Allow" on the TV again.
VOLUME /data

ENV PIXASSO_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

USER pixasso
CMD ["python", "-m", "pixasso"]
