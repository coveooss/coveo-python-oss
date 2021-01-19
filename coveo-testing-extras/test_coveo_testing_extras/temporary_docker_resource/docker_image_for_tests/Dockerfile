FROM python:alpine
ADD index.html /webcontent/
EXPOSE 80
CMD ["python", "-m", "http.server", "80", "--directory", "/webcontent", "--bind", "0.0.0.0"]
