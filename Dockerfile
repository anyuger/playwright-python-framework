FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

# No screen in a container. The browser fixture in conftest.py reads HEADLESS.
ENV HEADLESS=true

CMD ["pytest"]