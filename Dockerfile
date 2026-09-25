FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

# Same options as pytest.ini minus --headed (no screen in a container)
CMD ["pytest", "--override-ini=addopts=--alluredir=allure-results --strict-markers"]