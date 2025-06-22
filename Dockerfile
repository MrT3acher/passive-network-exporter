# Use the official Python image from the Docker Hub
FROM python:3.12-slim

RUN sed -i 's/deb\.debian\.org/ftp.nl.debian.org/g' /etc/apt/sources.list.d/debian.sources
RUN echo 'Acquire::http::Proxy "http://172.16.0.6:8000/";' > /etc/apt/apt.conf.d/squid-deb-proxy.conf
RUN apt-get update
RUN apt-get install -y libpq-dev build-essential locales

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Run the application
ENTRYPOINT ["python3", "prometheus_http_sd.py"]