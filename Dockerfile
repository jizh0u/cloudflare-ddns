# ---- Base ----
FROM python:alpine AS base

#
# ---- Dependencies ----
FROM base AS dependencies
# install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt
 
#
# ---- Release ----
FROM dependencies AS release
# copy project source file(s)
WORKDIR /
COPY ddns.py .
COPY config.json .
CMD ["python", "-u", "/ddns.py", "--config_file=config.json"]
