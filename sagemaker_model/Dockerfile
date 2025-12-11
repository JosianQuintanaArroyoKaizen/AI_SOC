FROM python:3.11-slim

RUN pip install --no-cache-dir     scikit-learn==1.7.2     numpy==2.2.1     xgboost==2.1.3     flask     gunicorn     sagemaker-inference

# Copy inference code
COPY inference.py /opt/program/inference.py

ENV PATH="/opt/program:${PATH}"
ENV SAGEMAKER_PROGRAM=inference.py

WORKDIR /opt/program

# Set up SageMaker inference
ENTRYPOINT ["python", "-m", "sagemaker_inference", "serve"]
