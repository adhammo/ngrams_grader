# Use a lightweight official Python image as the base
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (git is required for cloning repos)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt ./

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files into the container
COPY . .

# Expose the port Streamlit runs on (default is 8501)
EXPOSE 8501

# Command to run the Streamlit application when the container starts
CMD ["streamlit", "run", "src/ui/app.py"]

# docker build -t ngrams-grader .
# docker run -p 8501:8501 ngrams-grader